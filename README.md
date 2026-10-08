# Proyek Basis Data Norton

Proyek ini mengelola transaksi langganan Norton dari kanal retail dan cobrand menggunakan SQLite. Fokus model operasionalnya adalah enam tabel: `channel`, `campaign`, `customer`, `pricing`, `device_profile`, dan `transaction_log`.

## Struktur

```text
basis-data/
├── data/          CSV sumber
├── database/      database operasional SQLite
├── sql/           schema.sql dan analisis.sql
├── scripts/       pipeline.py dan analisis_sql.py
├── outputs/       CSV hasil query
├── docs/          ERD
├── _archive/      berkas proyek lama yang disimpan
├── README.md
└── requirements.txt
```

Database aktif `database/norton_bisnis.db` berisi enam tabel operasional. Database awal di `basis-data/norton_bisnis.db` tidak ditimpa atau dipindahkan karena sedang digunakan proses lain saat reorganisasi.

## ETL

Pipeline membaca `retail_transaction_log.csv` dan `cobrandgen_transaction_log.csv`, menyeragamkan nama/format kolom, membentuk key dan atribut turunan dari nilai sumber, lalu memuat tabel referensi sebelum `transaction_log`. Foreign key diaktifkan dan `business_key` dipakai agar eksekusi ulang tidak menggandakan transaksi. `package.csv` disimpan sebagai dataset sumber, tetapi tidak digunakan karena Package tidak termasuk enam entitas operasional.

WSL Ubuntu, dari root proyek:

```bash
python3 -m pip install -r basis-data/requirements.txt
python3 basis-data/scripts/pipeline.py
python3 basis-data/scripts/analisis_sql.py
```

Untuk uji ETL tanpa menyentuh database aktif, arahkan ke file sementara:

```bash
python3 basis-data/scripts/pipeline.py --database /tmp/norton_test.db
python3 basis-data/scripts/analisis_sql.py --database /tmp/norton_test.db --output-dir /tmp/norton_outputs
```

## Analisis SQL

Query disimpan di `sql/analisis.sql` dan dijalankan melalui Pandas oleh `scripts/analisis_sql.py`:

```bash
python3 basis-data/scripts/analisis_sql.py
```

Hasil DataFrame ditampilkan di terminal dan CSV disimpan di `outputs/`. Analisis meliputi 10 transaksi pertama, informasi kanal, jumlah transaksi per kanal, ringkasan status, dan nilai transaksi per kanal. Total seluruh harga mencakup transaksi uji; pendapatan valid mengecualikan transaksi uji dan hanya menjumlah baris dengan `is_revenue_valid=1`.

## Status arsip

Folder `_archive/legacy/` menyimpan skema dan query lama yang membangun model analitik, notebook, grafik, cache, dan dokumentasi lama. Berkas tersebut tidak dipakai oleh pipeline aktif. Database awal tetap berada di lokasi semula karena terkunci saat reorganisasi; jangan gunakan untuk pipeline enam tabel.
