window.PageFilesforsatsPublic = {
  template: '#page-filesforsats-public',
  delimiters: ['${', '}'],
  data: function () {
    return {
      productId: '',
      product: null,        // PublicProduct — no hash inside
      loadError: false,

      // Buyer flow state machine
      // 'loading' | 'integrity_required' | 'integrity_ok' | 'awaiting_payment' | 'paid' | 'error'
      step: 'loading',

      integrityCode: '',
      integrityError: '',
      integrityLoading: false,
      integrityToken: null,

      invoiceLoading: false,
      paymentRequest: '',
      paymentHash: '',

      downloadReady: false
    }
  },

  computed: {
    shareUrl() {
      return window.location.href
    },
    fileSizeFormatted() {
      if (!this.product) return ''
      const bytes = this.product.file_size
      if (!bytes) return '—'
      const k = 1024
      const sizes = ['B', 'KB', 'MB', 'GB']
      const i = Math.floor(Math.log(bytes) / Math.log(k))
      return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
    }
  },

  methods: {
    // ── 1. Load product info ─────────────────────────────────────────────────
    async fetchProduct() {
      try {
        const { data } = await LNbits.api.request(
          'GET',
          `/filesforsats/api/v1/products/${this.productId}/public`
        )
        this.product = data
        this.step = this.product.require_integrity ? 'integrity_required' : 'ready_for_invoice'
      } catch (err) {
        this.loadError = true
        this.step = 'error'
        console.warn('filesforsats: could not load product', err)
      }
    },

    // ── 2. Submit integrity code ─────────────────────────────────────────────
    async submitIntegrity() {
      if (!this.integrityCode.trim()) {
        this.integrityError = 'Please enter the integrity code.'
        return
      }
      this.integrityLoading = true
      this.integrityError = ''
      try {
        const { data } = await LNbits.api.request(
          'POST',
          `/filesforsats/api/v1/products/${this.productId}/verify`,
          null,
          { code: this.integrityCode.trim() }
        )
        this.integrityToken = data.integrity_token
        this.step = 'integrity_ok'
      } catch (err) {
        // Never show the expected hash — only generic messages
        const status = err?.response?.status
        if (status === 422) {
          this.integrityError = 'Invalid integrity code. Please check and try again.'
        } else {
          this.integrityError = 'Verification failed. Please try again later.'
        }
      } finally {
        this.integrityLoading = false
      }
    },

    // ── 3. Create invoice ────────────────────────────────────────────────────
    async createInvoice() {
      this.invoiceLoading = true
      try {
        const { data } = await LNbits.api.request(
          'POST',
          `/filesforsats/api/v1/products/${this.productId}/invoice`,
          null,
          { integrity_token: this.integrityToken || '' }
        )
        this.paymentRequest = data.payment_request
        this.paymentHash = data.payment_hash
        this.step = 'awaiting_payment'
        this.waitForPayment(this.paymentHash)
      } catch (err) {
        LNbits.utils.notifyApiError(err)
      } finally {
        this.invoiceLoading = false
      }
    },

    // ── 4. Wait for payment (WebSocket + polling fallback) ───────────────────
    async waitForPayment(paymentHash) {
      // Primary: WebSocket
      try {
        const url = new URL(window.location)
        url.protocol = url.protocol === 'https:' ? 'wss' : 'ws'
        url.pathname = `/api/v1/ws/${paymentHash}`
        const ws = new WebSocket(url)
        ws.addEventListener('message', async ({ data }) => {
          const msg = JSON.parse(data)
          if (msg.pending === false) {
            ws.close()
            await this.onPaymentConfirmed()
          }
        })
        ws.addEventListener('error', () => {
          ws.close()
          this.startPolling(paymentHash)
        })
        // Also start a polling safety net in case the WS disconnects
        this._pollInterval = setInterval(() => this.pollStatus(paymentHash), 5000)
      } catch (_) {
        this.startPolling(paymentHash)
      }
    },

    startPolling(paymentHash) {
      this._pollInterval = setInterval(() => this.pollStatus(paymentHash), 5000)
    },

    async pollStatus(paymentHash) {
      try {
        const { data } = await LNbits.api.request(
          'GET',
          `/filesforsats/api/v1/purchases/${paymentHash}/status`
        )
        if (data.paid) {
          clearInterval(this._pollInterval)
          await this.onPaymentConfirmed()
        }
      } catch (_) { /* silent — will retry */ }
    },

    async onPaymentConfirmed() {
      clearInterval(this._pollInterval)
      this.step = 'paid'
      this.downloadReady = true
      Quasar.Notify.create({ type: 'positive', message: 'Payment confirmed! Your download is ready.' })
    },

    // ── 5. Trigger download ──────────────────────────────────────────────────
    downloadFile() {
      // Navigate to protected endpoint; server validates payment and streams file
      const a = document.createElement('a')
      a.href = `/filesforsats/api/v1/download/${this.paymentHash}`
      a.download = this.product?.file_name || 'download'
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
    }
  },

  async created() {
    this.productId = this.$route.params.id
    await this.fetchProduct()
  },

  beforeUnmount() {
    clearInterval(this._pollInterval)
  }
}
