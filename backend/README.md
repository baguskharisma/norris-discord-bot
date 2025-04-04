# Norris Discord Bot

Bot Discord ini memungkinkan pengguna untuk mengunggah dokumen (PDF, DOCX, TXT) ke saluran Discord dan mendapatkan ringkasan yang dihasilkan oleh AI menggunakan API LLM. Bot ini juga dilengkapi dengan web interface untuk memantau status bot secara real-time.

## Fitur

- **Pemrosesan Dokumen**: Mengekstrak teks dari file PDF, DOCX, dan TXT
- **Ringkasan AI**: Merangkum konten dokumen menggunakan model Llama 3.3 70B Versatile
- **Tanya Jawab**: Ajukan pertanyaan spesifik tentang dokumen dan dapatkan jawaban yang akurat
- **Memori Dokumen**: Bot mengingat dokumen untuk pertanyaan lanjutan di saluran yang sama
- **Mudah Digunakan**: Perintah sederhana untuk ringkasan dokumen dan tanya jawab
- **Web Dashboard**: Memantau status bot melalui web interface
- **Update Real-time**: Melacak aktivitas dan status bot

## Komponen

### Bot Discord

- Memproses unggahan dokumen di saluran Discord
- Mengekstrak teks dan menghasilkan ringkasan
- Menjawab pertanyaan spesifik tentang dokumen
- Menyimpan konten dokumen untuk pertanyaan lanjutan
- Memberikan umpan balik tentang status pemrosesan

### Web Interface

- Menampilkan status bot saat ini (Online, Bekerja, Kesalahan, dll.)
- Menampilkan informasi waktu aktif
- Melacak aktivitas bot terbaru
- Pembaruan otomatis untuk menunjukkan pembaruan real-time

## Perintah

- `/summarize`: Merangkum dokumen yang dilampirkan
- `/ask <pertanyaan>`: Ajukan pertanyaan tentang dokumen yang diproses terakhir
- `/help_summarize`: Menampilkan informasi bantuan

## Persyaratan

- Python 3.8+
- Node.js 16+
- Discord Bot Token
- Groq API Key

## Penggunaan

### Bot Discord

1. Invite bot ke server Discord
2. Upload dokumen ke saluran
3. Ketik `/summarize` dalam pesan dengan lampiran
4. Tunggu bot memproses dokumen dan memberikan ringkasan
5. Ajukan pertanyaan tentang dokumen dengan mengetik `/ask` diikuti dengan pertanyaan Anda
   Contoh: `/ask Apa kesimpulan utama dari dokumen ini?`

### Web Interface

1. Akses antarmuka web di URL
2. Lihat status dan waktu aktif bot saat ini
3. Pantau aktivitas terbaru dan status pemrosesan

## Tipe Dokumen yang Didukung

- PDF (.pdf)
- Word Documents (.docx)
- Text Files (.txt)

## Instruksi Pengaturan

1. Pastikan variabel lingkungan berikut diatur:

   - `DISCORD_TOKEN`: Token bot Discord
   - `GROQ_API_KEY`: Kunci API Groq

2. Instal dependensi:

   ```bash
   pip install -r requirements.txt
   npm install
   ```

3. Jalankan aplikasi:

   ```bash
   # Menggunakan workflow yang dikonfigurasi
   npm run start

   # atau secara manual
   gunicorn --bind 0.0.0.0:5000 --reuse-port --reload main:app
   ```

## Arsitektur

Aplikasi ini menggunakan arsitektur hybrid:

- **Backend (Python)**:

  - `main.py`: Titik masuk aplikasi, menginisialisasi bot dan server web
  - `discord_bot.py`: Implementasi bot Discord dan penanganan perintah
  - `document_parser.py`: Logika ekstraksi teks dokumen
  - `groq_client.py`: Integrasi API Groq untuk pemrosesan LLM
  - `app.py`: Aplikasi Flask dengan endpoint API untuk status

- **Frontend (Next.js)**:
  - `app/page.tsx`: Interface dashboard utama
  - `app/api/bot-status/route.ts`: API route untuk komunikasi backend
  - `app/globals.css`: Styling untuk web interface
  - `next.config.ts`: Konfigurasi untuk pemrosesan API

## Deployment

Aplikasi ini dirancang untuk diterapkan sebagai berikut:

1. Implementasikan backend Python ke server yang mendukung aplikasi Python
2. Siapkan variabel lingkungan yang diperlukan
3. Konfigurasikan frontend Next.js untuk berkomunikasi dengan backend

## Batasan

- Dokumen besar mungkin terpotong karena batasan token API
- Kualitas ringkasan tergantung pada model LLM yang digunakan
- Memerlukan token Discord maupun API key Groq untuk berfungsi dengan baik
