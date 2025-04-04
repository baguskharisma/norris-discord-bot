# Troubleshooting Guide

Panduan ini mencakup masalah umum yang mungkin ditemui saat mengatur atau menggunakan Norris Discord Bot.

## Bot Tidak Terhubung ke Discord

**Masalah:** Bot muncul sebagai "Offline" di web interface dan tidak merespon perintah di Discord.

**Solusi:**

1. **Periksa Token Discord**

   - Verifikasi bahwa token Discord telah disetel dengan benar di variabel lingkungan
   - Pastikan token tersebut valid dan belum di-reset atau dicabut
   - Pastikan bot telah diundang ke server dengan izin yang tepat

2. **Masalah Jaringan**

   - Pastikan server terhubung ke internet
   - Periksa apakah ada aturan firewall yang memblokir koneksi Discord
   - Verifikasi bahwa API Discord tidak mengalami gangguan

3. **Masalah Kode Bot**
   - Periksa log untuk pesan kesalahan tertentu
   - Pastikan kode yang berjalan adalah versi yang terbaru
   - Verifikasi bahwa discord.py telah terinstal dengan benar

## Ringkasan Tidak Berfungsi

**Masalah:** Bot mengenali perintah tetapi tidak memberikan ringkasan.

**Solusi:**

1. **Groq API Key**

   - Verifikasi bahwa kunci API Groq telah disetel dengan benar di variabel lingkungan
   - Periksa apakah akun Groq memiliki cukup kredit/kuota
   - Pastikan API key belum expired atau dicabut

2. **Tipe Dokumen**

   - Pastikan tipe dokumen didukung (PDF, DOCX, TXT)
   - Periksa bahwa dokumen tidak kosong atau corrupt
   - Verifikasi bahwa dokumen tidak dilindungi password

3. **Ukuran Dokumen**
   - Dokumen besar mungkin mencapai batas token - coba dengan dokumen yang lebih kecil
   - Periksa apakah ada log pengecualian yang terkait dengan ukuran dokumen

## Masalah Web Interface

**Issue:** Dashboard web tidak dimuat atau menampilkan informasi yang tidak akurat.

**Solusi:**

1. **Konfigurasi Server**

   - Pastikan server berjalan di port 3000
   - Periksa apakah frontend Next.js sudah dikonfigurasi dengan benar untuk berkomunikasi dengan backend
   - Verifikasi bahwa semua paket yang diperlukan telah diinstal

2. **Koneksi API**

   - Cari kesalahan CORS di konsol browser
   - Periksa apakah endpoint API berfungsi dengan baik
   - Verifikasi konektivitas jaringan antara frontend dan backend

3. **Data Usang**
   - Coba segarkan halaman atau hapus cache browser
   - Periksa apakah fungsi penyegaran otomatis berfungsi

## Kesalahan Pemrosesan Dokumen

**Masalah:** Bot tidak dapat mengekstrak teks dari dokumen tertentu.

**Solusi:**

1. **Ketergantungan**

   - Pastikan semua package yang diperlukan telah diinstal (PyPDF2, python-docx)
   - Periksa apakah ada konflik versi ketergantungan

2. **Pemformatan Dokumen**

   - Beberapa dokumen PDF menggunakan pemformatan yang kompleks dan sulit untuk diproses
   - Dokumen yang dipindai dengan OCR mungkin tidak dapat dibaca dengan PyPDF2
   - Cobalah mengonversi dokumen ke format yang lebih sederhana

3. **Corrupt File**
   - Pastikan dokumen tidak korup
   - Cobalah menyimpan ulang dokumen dalam aplikasi aslinya

## Masalah Pengenalan Perintah

**Masalah:** Bot tidak mengenali perintah atau merespon dengan kesalahan.

**Solusi:**

1. **Command**

   - Pastikan awalan perintah benar (`/`)
   - Periksa kesalahan ketik dalam nama perintah
   - Verifikasi berkas yang dilampirkan dengan perintah `/summarize` benar

2. **Bot Permissions**

   - Periksa apakah bot memiliki izin yang tepat di channel
   - Verifikasi bahwa bot dapat membaca pesan dan mengirim respon
   - Pastikan 'Message Content' diaktifkan di Discord Developer Portal

3. **Discord Rate Limits**
   - Jika bot digunakan secara ekstensif, Discord mungkin membatasi laju penggunaannya
   - Periksa log untuk peringatan rate limit

## Environment Variables

**Masalah:** Environment variables tidak dikenali.

**Solusi:**

1. **Nama Variabel**

   - Periksa kembali bahwa nama variabel persis seperti yang diharapkan:
     - `DISCORD_TOKEN`
     - `GROQ_API_KEY`

2. **Variable Scope**

   - Pastikan variabel disetel pada level sistem atau dalam konfigurasi yang sesuai
   - Jika menggunakan platform penyebaran, periksa pengaturan variabel lingkungan

3. **Karakter Khusus**
   - Jika token mengandung karakter khusus, pastikan karakter tersebut disisipkan dengan benar

## Masalah Kinerja

**Masalah:** Bot lambat merespon atau mengalami crash dengan dokumen besar.

**Solusi:**

1. **Server Resources**

   - Periksa apakah server memiliki CPU dan memori yang cukup
   - Pertimbangkan untuk meingkatkan paket hosting jika resources terbatas

2. **Document Chunking**

   - Untuk dokumen yang sangat besar, bot mencoba membaginya - periksa logika ini
   - Sesuaikan ukuran chunk berdasarkan kebutuhan

3. **Batasan API**
   - Periksa batas laju dan batas token
