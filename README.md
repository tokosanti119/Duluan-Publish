# Duluan (gratis)

Menarik RSS media nasional + Google Trends Indonesia, lalu membuat halaman `docs/index.html`
berisi berita terbaru dan topik yang "mulai naik" (muncul di 3+ media dalam 3 jam).

## Cara A — Otomatis tanpa laptop menyala (GitHub, gratis)
1. Buat akun di github.com, lalu buat repository baru bernama `radar-berita` (Public).
2. Upload SEMUA isi folder ini (termasuk folder `.github` dan `docs`) ke repository.
   Tips: di laptop, tarik-lepas file ke halaman repository. Pastikan `.github/workflows/update.yml` ikut terunggah.
3. Buka tab **Settings → Pages**. Pada "Branch" pilih `main` dan folder `/docs`, lalu Save.
4. Buka tab **Actions**, pilih "update-radar", klik **Run workflow** sekali untuk mencoba.
5. Setelah 1-2 menit, alamat radarmu muncul di Settings → Pages
   (bentuknya `https://NAMAKAMU.github.io/radar-berita/`). Buka dari HP, lalu "Tambahkan ke layar utama".

Selanjutnya halaman diperbarui otomatis tiap ~5 menit (batas minimum GitHub, kadang telat beberapa menit).

## Cara B — Di laptop sendiri (bisa tiap 1-2 menit)
Pasang Python 3, lalu jalankan:
    python fetch_news.py --loop 120
Buka file `docs/index.html` di browser. Hanya jalan selama laptop menyala dan online.

## Catatan
- Sumber RSS bisa berubah alamat. Yang gagal otomatis dilewati dan ditulis di bagian bawah halaman.
  Edit daftar `FEEDS` di `fetch_news.py` untuk menambah/mengganti media.
- "Mulai naik" adalah sinyal otomatis, bukan prediksi viral. Selalu verifikasi sebelum menulis.
- X, Threads, dan Instagram tidak ikut dipantau karena tidak ada akses data gratis.
