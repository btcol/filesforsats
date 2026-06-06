window.PageFilesforsats = {
  template: '#page-filesforsats',
  delimiters: ['${', '}'],
  data: function () {
    return {
      // ── product list ──────────────────────────────────────────────────
      productsList: [],
      productsTable: {
        search: '',
        loading: false,
        columns: [
          {name: 'name',        align: 'left',   label: 'Name',         field: 'name',        sortable: true},
          {name: 'price_sats',  align: 'right',  label: 'Price (sats)', field: 'price_sats',  sortable: true},
          {name: 'file_name',   align: 'left',   label: 'File',         field: 'file_name',   sortable: false},
          {name: 'require_integrity', align: 'center', label: 'Integrity gate', field: 'require_integrity', sortable: true},
          {name: 'updated_at',  align: 'left',   label: 'Updated',      field: 'updated_at',  sortable: true},
        ],
        pagination: {sortBy: 'updated_at', rowsPerPage: 10, page: 1, descending: true, rowsNumber: 10}
      },

      // ── create / edit dialog ──────────────────────────────────────────
      productDialog: {
        show: false,
        loading: false,
        data: {
          name: '',
          description: '',
          price_sats: 1000,
          wallet_id: null,
          require_integrity: true,
          file: null
        }
      },

      // ── hash reveal dialog (shown after successful upload) ────────────
      hashDialog: {
        show: false,
        productName: '',
        productId: '',
        hash: '',
        shareLink: '',
        copied: false
      }
    }
  },

  watch: {
    'productsTable.search': {
      handler () { this.getProducts() }
    }
  },

  methods: {
    // ── UI helpers ───────────────────────────────────────────────────────
    dateFromNow (date) { return moment(date).fromNow() },

    formatBytes (bytes) {
      if (!bytes) return '0 B'
      const k = 1024
      const sizes = ['B', 'KB', 'MB', 'GB']
      const i = Math.floor(Math.log(bytes) / Math.log(k))
      return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
    },

    // ── product CRUD ─────────────────────────────────────────────────────
    showNewProductForm () {
      this.productDialog.data = {
        name: '',
        description: '',
        price_sats: 1000,
        wallet_id: this.g.user.walletOptions[0]?.value || null,
        require_integrity: true,
        file: null
      }
      this.productDialog.show = true
    },

    onFileSelected (file) {
      this.productDialog.data.file = file
    },

    async saveProduct () {
      const d = this.productDialog.data

      if (!d.name || !d.name.trim()) {
        Quasar.Notify.create({type: 'negative', message: 'Product name is required.'})
        return
      }
      if (!d.price_sats || d.price_sats < 1) {
        Quasar.Notify.create({type: 'negative', message: 'Price must be at least 1 sat.'})
        return
      }
      if (!d.wallet_id) {
        Quasar.Notify.create({type: 'negative', message: 'Select a wallet.'})
        return
      }
      if (!d.file) {
        Quasar.Notify.create({type: 'negative', message: 'Please select a file to upload.'})
        return
      }

      this.productDialog.loading = true
      try {
        const form = new FormData()
        form.append('name', d.name.trim())
        form.append('description', d.description || '')
        form.append('price_sats', String(d.price_sats))
        form.append('wallet_id', d.wallet_id)
        form.append('require_integrity', String(d.require_integrity))
        form.append('file', d.file)

        // Use fetch directly for multipart — LNbits.api.request sets JSON content-type
        const resp = await fetch('/filesforsats/api/v1/products', {
          method: 'POST',
          headers: {
            'X-Api-Key': this.g.user.wallets.find(w => w.id === d.wallet_id)?.adminkey || ''
          },
          body: form
        })
        if (!resp.ok) {
          const err = await resp.json().catch(() => ({detail: resp.statusText}))
          throw new Error(err.detail || resp.statusText)
        }
        const product = await resp.json()

        // Show the hash to the seller immediately after upload
        this.hashDialog = {
          show: true,
          productName: product.name,
          productId: product.id,
          hash: product.sha256_hash,
          shareLink: window.location.origin + '/filesforsats/' + product.id,
          copied: false
        }

        this.productDialog.show = false
        await this.getProducts()
        Quasar.Notify.create({type: 'positive', message: 'Product created successfully!'})
      } catch (err) {
        Quasar.Notify.create({type: 'negative', message: err.message || 'Failed to create product.'})
      } finally {
        this.productDialog.loading = false
      }
    },

    async getProducts (props) {
      try {
        this.productsTable.loading = true
        const params = LNbits.utils.prepareFilterQuery(this.productsTable, props)
        const {data} = await LNbits.api.request(
          'GET',
          `/filesforsats/api/v1/products/paginated?${params}`,
          null
        )
        this.productsList = data.data
        this.productsTable.pagination.rowsNumber = data.total
      } catch (err) {
        LNbits.utils.notifyApiError(err)
      } finally {
        this.productsTable.loading = false
      }
    },

    showHash (product) {
      this.hashDialog = {
        show: true,
        productName: product.name,
        productId: product.id,
        hash: product.sha256_hash,
        shareLink: window.location.origin + '/filesforsats/' + product.id,
        copied: false
      }
    },

    copyHash () {
      navigator.clipboard.writeText(this.hashDialog.hash).then(() => {
        this.hashDialog.copied = true
        setTimeout(() => { this.hashDialog.copied = false }, 2000)
      })
    },

    copyShareLink () {
      navigator.clipboard.writeText(this.hashDialog.shareLink).then(() => {
        Quasar.Notify.create({type: 'positive', message: 'Link copied to clipboard!'})
      })
    },

    async deleteProduct (productId) {
      await LNbits.utils.confirmDialog('Delete this product and its file permanently?')
        .onOk(async () => {
          try {
            await LNbits.api.request('DELETE', `/filesforsats/api/v1/products/${productId}`, null)
            await this.getProducts()
            Quasar.Notify.create({type: 'positive', message: 'Product deleted.'})
          } catch (err) {
            LNbits.utils.notifyApiError(err)
          }
        })
    },

    publicLink (productId) {
      return window.location.origin + '/filesforsats/' + productId
    },

    openPublicLink (productId) {
      window.open(this.publicLink(productId), '_blank')
    },

    async exportProductsCSV () {
      await LNbits.utils.exportCSV(this.productsTable.columns, this.productsList,
        'files4sats_products_' + new Date().toISOString().slice(0, 10) + '.csv')
    }
  },

  async created () {
    await this.getProducts()
  }
}