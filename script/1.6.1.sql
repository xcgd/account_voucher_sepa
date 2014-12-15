-- Populate sepa batch company_id (was not done correctly before)
update account_voucher_sepa_batch set company_id = voucher.company_id from account_voucher voucher where voucher.batch_id = account_voucher_sepa_batch.id;

