# filesforsats — An [LNbits](https://github.com/lnbits/lnbits) Extension

> **Sell downloadable digital files through Bitcoin Lightning payments, with cryptographic file integrity verification built in.**

---

## How it works

### For the Seller

1. **Create a product** — Open the extension dashboard, fill in the product name, description, and price in sats.
2. **Upload your file** — Any single file is supported (documents, archives, images, software, audio, etc.). There is no directory upload.
3. **Get the integrity hash** — The server automatically computes the **SHA-256** hash of the uploaded file. You do not type it — the system generates it from the actual bytes on disk, eliminating human error.
4. **Share privately** — Copy the SHA-256 hash and the public product link. Send **both** to your buyer through a channel of your choice (Signal, email, etc.). The hash is the buyer's key; keep it out of public channels.

### For the Buyer

1. **Open the product link** — A public page shows the product name, description, file size, and price. No hash is ever shown here.
2. **Enter the integrity code** — Paste the SHA-256 hash the seller sent you. The server validates it server-side without revealing the expected value.
3. **Pay the invoice** — Once the code is validated, a Lightning invoice is generated. Scan the QR code or copy the invoice into any Lightning wallet.
4. **Download** — After payment is confirmed, a download button appears. The file is served directly from the backend — there is no public file URL.

---

## Security design

| Property                      | How it is enforced                                                                                 |
| ----------------------------- | -------------------------------------------------------------------------------------------------- |
| Hash never shown to buyer     | `PublicProduct` API model excludes `sha256_hash` by design                                         |
| Timing-safe code comparison   | `hmac.compare_digest()` — prevents timing attacks                                                  |
| No public file URLs           | Files are stored outside `static/` and served only through a guarded endpoint                      |
| Payment validated server-side | Download endpoint checks `purchase.paid == True` in the database before serving                    |
| Integrity bypass prevented    | Invoice creation re-validates the `integrity_token` server-side — frontend state is never trusted  |
| Path traversal blocked        | Uploaded files are renamed to UUIDs; resolved path is checked to stay within the storage directory |
| Large file support            | Files are streamed to disk in 64 KiB chunks — no full-file RAM load                                |

---

## Configuration

The maximum allowed upload size is defined in `services.py`:

```python
# services.py
MAX_UPLOAD_BYTES: int = 1 * 1024 * 1024 * 1024  # 1 GiB — change freely
```

Uploaded files are stored in `<lnbits_data_folder>/filesforsats/` — outside the web root.

---

## Supported file types

Any single file is accepted. Multi-file uploads and directory uploads are not supported. MIME type is inferred from the file extension.

---

## Requirements

- LNbits `>= 1.4.2`
- A funded LNbits wallet to receive payments

---

## Installation

Install via the LNbits Extension Manager or clone directly into your extensions directory:

```bash
cd lnbits/extensions
git clone https://github.com/lnbits/filesforsats filesforsats
```

Then enable the extension from the LNbits admin panel.

---

## API overview

| Method   | Endpoint                          | Auth          | Description                                |
| -------- | --------------------------------- | ------------- | ------------------------------------------ |
| `POST`   | `/api/v1/products`                | Seller        | Upload file and create product (multipart) |
| `GET`    | `/api/v1/products/paginated`      | Seller        | List products                              |
| `GET`    | `/api/v1/products/{id}`           | Seller        | Get product detail (includes SHA-256)      |
| `DELETE` | `/api/v1/products/{id}`           | Seller        | Delete product and file                    |
| `GET`    | `/api/v1/products/{id}/public`    | Public        | Get buyer-safe product info (no hash)      |
| `POST`   | `/api/v1/products/{id}/verify`    | Public        | Submit integrity code, receive token       |
| `POST`   | `/api/v1/products/{id}/invoice`   | Public        | Create Lightning invoice                   |
| `GET`    | `/api/v1/purchases/{hash}/status` | Public        | Poll payment status                        |
| `GET`    | `/api/v1/download/{hash}`         | Public (paid) | Download file after confirmed payment      |

---

## License

MIT — see [LICENSE](LICENSE)

---

## Support & Contributions ⚡️

Thank you for using **filesforsats**!

If you find this extension useful and would like to support its ongoing development, maintenance, and new features, please consider making a Lightning donation. Your contributions directly help keep this project alive and continuously improving.

Every satoshi is deeply appreciated! 🧡

<div align="center">
  <img src="./filesforsats.svg" alt="Donate with Lightning" width="300"/>
</div>
