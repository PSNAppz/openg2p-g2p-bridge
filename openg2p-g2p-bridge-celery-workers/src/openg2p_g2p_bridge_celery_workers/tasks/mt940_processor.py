import logging
from datetime import datetime

import mt940
from openg2p_g2p_bridge_bank_connectors.bank_connectors import BankConnectorFactory
from openg2p_g2p_bridge_bank_connectors.bank_interface.bank_connector_interface import (
    BankConnectorInterface,
)
from openg2p_g2p_bridge_models.errors.codes import G2PBridgeErrorCodes
from openg2p_g2p_bridge_models.models import (
    AccountStatement,
    AccountStatementLob,
    BenefitProgramConfiguration,
    DisbursementBatchControl,
    DisbursementErrorRecon,
    DisbursementRecon,
    ProcessStatus,
)
from sqlalchemy.orm import sessionmaker

from ..app import celery_app, get_engine
from ..config import Settings

_config = Settings.get_config()
_logger = logging.getLogger(_config.logging_default_logger_name)
_engine = get_engine()


@celery_app.task(name="mt940_processor_worker")
def mt940_processor_worker(statement_id: str):
    _logger.info(f"Processing account statement with statement_id: {statement_id}")
    session_maker = sessionmaker(bind=_engine, expire_on_commit=False)

    with session_maker() as session:
        account_statement = (
            session.query(AccountStatement)
            .filter(AccountStatement.statement_id == statement_id)
            .first()
        )

        if not account_statement:
            return

        lob = (
            session.query(AccountStatementLob)
            .filter(AccountStatementLob.statement_id == statement_id)
            .first()
        )

        if not lob:
            return

        try:
            # Parsing header section
            account_number_parser = mt940.tags.AccountIdentification()
            statement_number_parser = mt940.tags.StatementNumber()
            transaction_reference_parser = mt940.tags.TransactionReferenceNumber()

            statement_parser = mt940.tags.Statement()
            mt940_statement = mt940.models.Transactions(
                processors={
                    "pre_statement": [mt940.processors.add_currency_pre_processor("")],
                },
                tags={
                    account_number_parser.id: account_number_parser,
                    statement_number_parser.id: statement_number_parser,
                    transaction_reference_parser.id: transaction_reference_parser,
                    statement_parser.id: statement_parser,
                },
            )

            mt940_statement.parse(lob.statement_lob)

            account_statement.account_number = mt940_statement.data.get(
                "account_identification", ""
            )
            account_statement.reference_number = mt940_statement.data.get(
                "transaction_reference", ""
            )
            account_statement.statement_number = mt940_statement.data.get(
                "statement_number", ""
            )
            account_statement.sequence_number = mt940_statement.data.get(
                "sequence_number", ""
            )
            _logger.info("Parsed account statement header")
            # Get the benefit program configuration
            benefit_program_configuration = (
                session.query(BenefitProgramConfiguration)
                .filter(
                    BenefitProgramConfiguration.sponsor_bank_account_number
                    == account_statement.account_number
                )
                .first()
            )
            if not benefit_program_configuration:
                account_statement.statement_process_status = ProcessStatus.ERROR
                account_statement.statement_process_error_code = (
                    G2PBridgeErrorCodes.INVALID_ACCOUNT_NUMBER.value
                )
                account_statement.statement_process_timestamp = datetime.utcnow()
                account_statement.statement_process_attempts += 1
                session.commit()
                return

            bank_connector: BankConnectorInterface = (
                BankConnectorFactory.get_component().get_bank_connector(
                    benefit_program_configuration.sponsor_bank_code
                )
            )

            # Parsing transactions
            parsed_transactions_d = []
            parsed_transactions_rd = []
            entry_sequence = 0
            for transaction in mt940_statement:
                entry_sequence += 1
                debit_credit_indicator = transaction.data["status"]

                if debit_credit_indicator in ["D"]:
                    parsed_transaction = construct_parsed_transaction(
                        bank_connector,
                        debit_credit_indicator,
                        entry_sequence,
                        transaction,
                    )
                    parsed_transactions_d.append(parsed_transaction)

                if debit_credit_indicator in ["RD"]:
                    parsed_transaction = construct_parsed_transaction(
                        bank_connector,
                        debit_credit_indicator,
                        entry_sequence,
                        transaction,
                    )
                    parsed_transactions_rd.append(parsed_transaction)

            # End of for loop of mt940 statement transactions
            disbursement_error_recons = []
            disbursement_recons = []

            # Process only debit transactions
            for parsed_transaction in parsed_transactions_d:
                bank_disbursement_batch_id = get_bank_batch_id(parsed_transaction, session)

                if not bank_disbursement_batch_id:
                    disbursement_error_recons.append(
                        construct_disbursement_error_recon(
                            statement_id,
                            account_statement.statement_number,
                            account_statement.sequence_number,
                            parsed_transaction,
                            G2PBridgeErrorCodes.INVALID_DISBURSEMENT_ID,
                        )
                    )
                    continue

                disbursement_recon = get_disbursement_recon(parsed_transaction, session)

                if disbursement_recon:
                    disbursement_error_recons.append(
                        construct_disbursement_error_recon(
                            statement_id,
                            account_statement.statement_number,
                            account_statement.sequence_number,
                            parsed_transaction,
                            G2PBridgeErrorCodes.DUPLICATE_DISBURSEMENT,
                        )
                    )
                    continue

                disbursement_recon = construct_new_disbursement_recon(
                    bank_disbursement_batch_id,
                    parsed_transaction,
                    statement_id,
                    account_statement.statement_number,
                    account_statement.sequence_number,
                )
                disbursement_recons.append(disbursement_recon)

            # End of for loop for parsed transactions - debit
            session.add_all(disbursement_recons)
            session.add_all(disbursement_error_recons)

            # Start processing reversal transactions - rd
            for parsed_transaction in parsed_transactions_rd:
                bank_disbursement_batch_id = get_bank_batch_id(parsed_transaction, session)

                if not bank_disbursement_batch_id:
                    disbursement_error_recons.append(
                        construct_disbursement_error_recon(
                            statement_id,
                            account_statement.statement_number,
                            account_statement.sequence_number,
                            parsed_transaction,
                            G2PBridgeErrorCodes.INVALID_DISBURSEMENT_ID,
                        )
                    )
                    continue

                disbursement_recon = get_disbursement_recon(parsed_transaction, session)

                if not disbursement_recon:
                    disbursement_error_recons.append(
                        construct_disbursement_error_recon(
                            statement_id,
                            account_statement.statement_number,
                            account_statement.sequence_number,
                            parsed_transaction,
                            G2PBridgeErrorCodes.INVALID_REVERSAL,
                        )
                    )
                else:
                    update_existing_disbursement_recon(
                        disbursement_recon,
                        parsed_transaction,
                        statement_id,
                        account_statement.statement_number,
                        account_statement.sequence_number,
                    )
                    disbursement_recons.append(disbursement_recon)

            # End of for loop for parsed transactions - rd
            session.add_all(disbursement_recons)
            session.add_all(disbursement_error_recons)

            # Update account statement with parsed data
            account_statement.statement_process_status = ProcessStatus.PROCESSED
            account_statement.statement_process_error_code = None
            account_statement.statement_process_timestamp = datetime.utcnow()
            account_statement.statement_process_attempts += 1

            session.add(account_statement)

            session.commit()
            _logger.info(
                f"Processed account statement for account number: {account_statement.account_number}"
            )

        except Exception as e:
            _logger.error(
                f"Error processing account statement for statement id: {statement_id}"
                f" with error: {str(e)}",
            )
            account_statement.statement_process_status = ProcessStatus.PENDING
            account_statement.statement_process_error_code = str(e)
            account_statement.statement_process_timestamp = datetime.utcnow()
            account_statement.statement_process_attempts += 1
            session.commit()
            raise e


def get_disbursement_recon(parsed_transaction, session):
    disbursement_recon = (
        session.query(DisbursementRecon)
        .filter(
            DisbursementRecon.disbursement_id
            == parsed_transaction["disbursement_id"]
        )
        .first()
    )
    return disbursement_recon


def get_bank_batch_id(parsed_transaction, session):
    bank_disbursement_batch_id = (
        session.query(DisbursementBatchControl)
        .filter(
            DisbursementBatchControl.disbursement_id
            == parsed_transaction["disbursement_id"]
        )
        .first()
        .bank_disbursement_batch_id
    )
    return bank_disbursement_batch_id


def construct_disbursement_error_recon(
    statement_id,
    statement_number,
    statement_sequence,
    parsed_transaction,
    g2p_bridge_error_code,
):
    return DisbursementErrorRecon(
        statement_id=statement_id,
        statement_number=statement_number,
        statement_sequence=statement_sequence,
        entry_sequence=parsed_transaction["remittance_entry_sequence"],
        entry_date=parsed_transaction["remittance_entry_date"],
        value_date=parsed_transaction["remittance_value_date"],
        error_reason=g2p_bridge_error_code,
        disbursement_id=parsed_transaction["disbursement_id"],
        bank_reference_number=parsed_transaction["remittance_reference_number"],
        active=True,
    )


def update_existing_disbursement_recon(
    disbursement_recon,
    parsed_transaction,
    statement_id,
    statement_number,
    statement_sequence,
):
    disbursement_recon.reversal_found = True
    disbursement_recon.reversal_statement_id = statement_id
    disbursement_recon.reversal_statement_number = statement_number
    disbursement_recon.reversal_statement_sequence = statement_sequence
    disbursement_recon.reversal_entry_sequence = parsed_transaction[
        "reversal_entry_sequence"
    ]
    disbursement_recon.reversal_entry_date = parsed_transaction["reversal_entry_date"]
    disbursement_recon.reversal_value_date = parsed_transaction["reversal_value_date"]
    disbursement_recon.reversal_reason = parsed_transaction["reversal_reason"]


def construct_new_disbursement_recon(
    bank_disbursement_batch_id,
    parsed_transaction,
    statement_id,
    statement_number,
    statement_sequence,
):
    disbursement_recon = DisbursementRecon(
        bank_disbursement_batch_id=bank_disbursement_batch_id,
        disbursement_id=parsed_transaction["disbursement_id"],
        beneficiary_name_from_bank=parsed_transaction["beneficiary_name_from_bank"],
        remittance_reference_number=parsed_transaction["remittance_reference_number"],
        remittance_statement_id=statement_id,
        remittance_statement_number=statement_number,
        remittance_statement_sequence=statement_sequence,
        remittance_entry_sequence=parsed_transaction["remittance_entry_sequence"],
        remittance_entry_date=parsed_transaction["remittance_entry_date"],
        remittance_value_date=parsed_transaction["remittance_value_date"],
        active=True,
    )
    return disbursement_recon


def construct_parsed_transaction(
    bank_connector,
    debit_credit_indicator,
    entry_sequence,
    transaction,
) -> dict:
    parsed_transaction = {}
    transaction_amount = transaction.data["amount"].amount
    customer_reference = transaction.data["customer_reference"]
    remittance_reference_number = transaction.data["bank_reference"]
    narratives = transaction.data["transaction_details"].split("\n")
    disbursement_id = bank_connector.retrieve_disbursement_id(
        remittance_reference_number, customer_reference, narratives
    )
    beneficiary_name_from_bank = None
    remittance_entry_sequence = None
    remittance_entry_date = None
    remittance_value_date = None

    reversal_found = False
    reversal_entry_sequence = None
    reversal_entry_date = None
    reversal_value_date = None
    reversal_reason = None

    if debit_credit_indicator == "D":
        reversal_found = False
        beneficiary_name_from_bank = bank_connector.retrieve_beneficiary_name(
            narratives
        )
        remittance_entry_sequence = entry_sequence
        remittance_entry_date = transaction.data["entry_date"]
        remittance_value_date = transaction.data["date"]

    if debit_credit_indicator == "RD":
        reversal_found = True
        reversal_entry_sequence = entry_sequence
        reversal_entry_date = transaction.data["entry_date"]
        reversal_value_date = transaction.data["date"]
        reversal_reason = bank_connector.retrieve_reversal_reason(narratives)

    parsed_transaction.update(
        {
            "disbursement_id": disbursement_id,
            "transaction_amount": transaction_amount,
            "debit_credit_indicator": debit_credit_indicator,
            "beneficiary_name_from_bank": beneficiary_name_from_bank,
            "remittance_reference_number": remittance_reference_number,
            "remittance_entry_sequence": remittance_entry_sequence,
            "remittance_entry_date": remittance_entry_date,
            "remittance_value_date": remittance_value_date,
            "reversal_found": reversal_found,
            "reversal_entry_sequence": reversal_entry_sequence,
            "reversal_entry_date": reversal_entry_date,
            "reversal_value_date": reversal_value_date,
            "reversal_reason": reversal_reason,
        }
    )
    return parsed_transaction
