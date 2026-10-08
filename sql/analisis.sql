-- query: 10_transaksi_pertama
SELECT id, business_key, channel_id, transaction_id, status_activated,
       price, is_revenue_valid, duration_days, is_churn
FROM transaction_log
ORDER BY id
LIMIT 10;

-- query: informasi_channel
SELECT c.channel_id, c.channel_name, c.description,
       COUNT(t.id) AS jumlah_transaksi
FROM channel c
LEFT JOIN transaction_log t ON t.channel_id = c.channel_id
GROUP BY c.channel_id, c.channel_name, c.description
ORDER BY c.channel_id;

-- query: transaksi_per_channel
SELECT c.channel_id, c.channel_name, COUNT(t.id) AS jumlah_transaksi
FROM channel c
LEFT JOIN transaction_log t ON t.channel_id = c.channel_id
GROUP BY c.channel_id, c.channel_name
ORDER BY jumlah_transaksi DESC;

-- query: ringkasan_status
SELECT status_activated,
       COUNT(*) AS jumlah_transaksi,
       SUM(CASE WHEN is_revenue_valid = 1 AND is_test = 0 THEN price ELSE 0 END) AS pendapatan_valid,
       SUM(is_churn) AS jumlah_churn
FROM transaction_log
GROUP BY status_activated
ORDER BY jumlah_transaksi DESC;

-- query: nilai_transaksi_per_channel
SELECT c.channel_id,
       c.channel_name,
       COUNT(t.id) AS jumlah_transaksi,
       SUM(COALESCE(t.price, 0)) AS total_nilai_seluruh_transaksi,
       SUM(CASE WHEN t.is_revenue_valid = 1 AND t.is_test = 0 THEN t.price ELSE 0 END) AS total_pendapatan_valid
FROM channel c
LEFT JOIN transaction_log t ON t.channel_id = c.channel_id
GROUP BY c.channel_id, c.channel_name
ORDER BY total_pendapatan_valid DESC;
