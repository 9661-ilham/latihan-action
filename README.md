# aq-service — starter P7 (CI/CD dan GitOps)

SS-302 Cloud Computing untuk Smart City · MTI UNLA · Pertemuan 7

Isi repository:

```text
.github/workflows/ci.yml        CI: uji -> build -> pindai Trivy -> push GHCR (tag sha-xxxxxxx)
app/                            kode layanan, Dockerfile, uji otomatis (pytest)
k8s/00-03                       manifest Kubernetes dari P6 (tanpa HPA)
argocd/application.yaml         objek Application Argo CD yang menunjuk ke folder k8s/
argocd/repo-secret.example.yaml contoh kredensial untuk repo private (JANGAN commit isinya)
```

Prasyarat: cluster k3d `ss302` dari P6 (laptop atau Codespaces), `kubectl`, akun GitHub. Argo CD butuh tambahan memori sekitar 1–1,5 GB; tutup aplikasi lain atau pakai Codespaces 4-core.

## Langkah 0 — Siapkan repository kelompok

1. Salin isi starter ini ke repository kelompok (struktur `app/`, `k8s/`, `argocd/`, `.github/`). Bila layanan kelompok berbeda, ganti isi `app/` dan sesuaikan uji di `app/tests/`.
2. Ganti `OWNER` di `k8s/02-deployment.yaml` dengan akun/organisasi GitHub (huruf kecil), dan `OWNER/REPO` di `argocd/application.yaml`.
3. Bila package `aq-service` sudah pernah di-push manual di P5, buka halaman package di GitHub → **Package settings → Manage Actions access** → tambahkan repository kelompok dengan peran **Write**. Tanpa ini push dari Actions ditolak (`permission_denied: write_package`).

## Langkah 1 — Jalankan CI

```bash
git add . && git commit -m "ci: tambah pipeline P7" && git push
```

Buka tab **Actions**. Run `ci` harus hijau: job `test` lalu `build-scan-push`. Ringkasan run menampilkan nama image, misalnya `ghcr.io/owner/aq-service:sha-1a2b3c4`. Cek juga halaman **Packages** di profil/organisasi.

Uji lokal sebelum push (opsional):

```bash
cd app && pip install -r requirements.txt -r requirements-dev.txt && pytest -q
```

### Bila CI gagal

| Gejala di log | Penyebab | Tindakan |
|---|---|---|
| Job `test` merah | Uji gagal | Baca baris `FAILED`, perbaiki kode atau uji |
| Langkah Trivy merah, tabel CVE `HIGH`/`CRITICAL` | Ada kerentanan yang sudah punya perbaikan, biasanya di base image atau paket Python | Jalankan ulang (base image `python:3.12-slim` diperbarui berkala); naikkan versi paket di `requirements.txt`; bila belum bisa diperbaiki, catat CVE di `.trivyignore` **beserta alasan** dan bahas di laporan. Jangan mengubah `exit-code` menjadi `"0"` diam-diam |
| `permission_denied: write_package` / `denied` saat push | Package milik akun lain atau repo belum diberi akses | Lihat Langkah 0 butir 3; pastikan nama owner huruf kecil |
| Workflow tidak berjalan setelah push | Perubahan tidak menyentuh `app/**` atau `ci.yml` | Wajar (filter `paths`); jalankan manual lewat **Run workflow** |

## Langkah 2 — Quality gate: buat pipeline gagal dengan sengaja

Di branch baru, rusak satu perilaku, misalnya ubah `ge=0` menjadi `ge=-100` pada field `pm25` di `app/app.py`. Buat pull request ke `main`.

Yang diharapkan: job `test` merah (`test_negative_pm25_rejected` gagal), job `build-scan-push` tidak berjalan, dan tidak ada image baru. Tutup PR tanpa merge (atau perbaiki lalu lihat hijau kembali).

## Langkah 3 — Pasang Argo CD di cluster

```bash
kubectl create namespace argocd
kubectl apply -n argocd --server-side --force-conflicts \
  -f https://raw.githubusercontent.com/argoproj/argo-cd/v3.6.2/manifests/install.yaml
kubectl -n argocd get pods -w      # tunggu semua Running (beberapa menit)
```

Buka UI (terminal terpisah):

```bash
kubectl -n argocd port-forward svc/argocd-server 8443:443
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d; echo
```

Buka `https://localhost:8443` (sertifikat self-signed; lanjutkan saja), login `admin` dengan password di atas. Jangan tampilkan password di laporan.

## Langkah 4 — Siapkan akses image dan repo

Image GHCR private butuh Secret `ghcr-cred` di namespace `ss302` (sama seperti P6; dibuat manual, **tidak** di Git):

```bash
kubectl create namespace ss302 --dry-run=client -o yaml | kubectl apply -f -
kubectl -n ss302 create secret docker-registry ghcr-cred \
  --docker-server=ghcr.io --docker-username=<username> --docker-password="$CR_PAT"
```

Repository kelompok **public**: tidak perlu apa-apa lagi. Repository **private**: salin `argocd/repo-secret.example.yaml` ke luar repo, isi, lalu `kubectl apply -f`.

## Langkah 5 — Daftarkan aplikasi

1. Isi tag image di `k8s/02-deployment.yaml` dengan tag dari Langkah 1, commit, push.
2. Terapkan Application:

```bash
kubectl apply -n argocd -f argocd/application.yaml
kubectl -n argocd get applications -w     # tunggu SYNC STATUS Synced, HEALTH Healthy
kubectl -n ss302 get deploy,pods -o wide
```

## Langkah 6 — Rilis versi baru lewat Git

1. Ubah kode (misalnya tambahkan field `"version"` di respons `/health`), push ke `main`, tunggu CI hijau, catat tag baru.
2. Ubah tag di `k8s/02-deployment.yaml`, commit dengan pesan jelas, push.
3. Argo CD memeriksa Git sekitar setiap 2–3 menit. Untuk lebih cepat, klik **Refresh** di UI.
4. Amati rolling update: `kubectl -n ss302 get pods -w`.

## Langkah 7 — Drift dan self-heal

```bash
kubectl -n ss302 scale deploy/aq-service --replicas=5
kubectl -n ss302 get pods -w
```

Dengan `selfHeal: true`, Argo CD mengembalikan jumlah replika ke nilai di Git (2) dalam hitungan detik. Coba juga `kubectl -n ss302 delete svc aq-service` lalu amati Service dibuat ulang.

## Langkah 8 — Rollback lewat Git

```bash
git revert <commit-perubahan-tag>   # kembalikan tag image sebelumnya
git push
```

Amati Argo CD menerapkan kembali versi lama. Bandingkan dengan `kubectl rollout undo` di P6: mengapa di GitOps rollback sebaiknya lewat Git?

## Pembersihan

```bash
kubectl delete -n argocd application aq-service
kubectl delete namespace argocd
```

Catatan: menghapus Application tanpa finalizer tidak menghapus objek di `ss302`. Hapus manual dengan `kubectl delete namespace ss302` bila perlu.

## Catatan keamanan

- Semua action di `ci.yml` dipin ke commit SHA. Tag action dapat dipindah oleh penyerang (kasus `tj-actions/changed-files`, Maret 2025; `aquasecurity/trivy-action`, Maret 2026).
- `GITHUB_TOKEN` hanya diberi `packages: write` di job yang mem-push.
- Jangan pernah commit token, password admin Argo CD, atau isi `repo-secret.yaml`.
