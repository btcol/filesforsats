<template id="page-filesforsats">
  <div class="row q-col-gutter-md">

    <!-- ═══════════════════════════════ LEFT COLUMN ══════════════════════════ -->
    <div class="col-12 col-md-8 col-lg-9 q-gutter-y-md">

      <div class="q-mt-lg row items-center">
        <span class="text-h5">My Products</span>
        <q-space></q-space>
        <q-btn @click="showNewProductForm()" unelevated color="primary" icon="add" label="New Product"></q-btn>
        <q-btn flat color="grey" icon="file_download" class="q-ml-sm" @click="exportProductsCSV">CSV</q-btn>
      </div>

      <q-card id="productsCard">
        <q-card-section>
          <div class="row items-center no-wrap q-mb-md">
            <div class="col">
              <q-input :label="$t('search')" dense v-model="productsTable.search">
                <template v-slot:before><q-icon name="search"></q-icon></template>
                <template v-slot:append>
                  <q-icon v-if="productsTable.search !== ''" name="close"
                    @click="productsTable.search = ''" class="cursor-pointer"></q-icon>
                </template>
              </q-input>
            </div>
          </div>

          <q-table
            dense flat
            :rows="productsList"
            row-key="id"
            :columns="productsTable.columns"
            v-model:pagination="productsTable.pagination"
            :loading="productsTable.loading"
            @request="getProducts"
          >
            <template v-slot:header="props">
              <q-tr :props="props">
                <q-th auto-width></q-th>
                <q-th v-for="col in props.cols" :key="col.name" :props="props">${ col.label }</q-th>
              </q-tr>
            </template>
            <template v-slot:body="props">
              <q-tr :props="props">
                <q-td auto-width>
                  <!-- Open public page -->
                  <q-btn flat dense size="xs" icon="launch" color="primary"
                    @click="openPublicLink(props.row.id)" class="q-mr-xs">
                    <q-tooltip>Open buyer page</q-tooltip>
                  </q-btn>
                  <!-- Show hash -->
                  <q-btn flat dense size="xs" icon="tag" color="teal"
                    @click="showHash(props.row)" class="q-mr-xs">
                    <q-tooltip>Show SHA-256 & share link</q-tooltip>
                  </q-btn>
                  <!-- Delete -->
                  <q-btn flat dense size="xs" icon="delete" color="negative"
                    @click="deleteProduct(props.row.id)" class="q-mr-xs">
                    <q-tooltip>Delete</q-tooltip>
                  </q-btn>
                </q-td>
                <q-td v-for="col in props.cols" :key="col.name" :props="props">
                  <div v-if="col.field === 'updated_at'"><span v-text="dateFromNow(col.value)"></span></div>
                  <div v-else-if="col.field === 'file_size'">${ formatBytes(col.value) }</div>
                  <div v-else-if="col.field === 'require_integrity'">
                    <q-badge :color="col.value ? 'teal' : 'grey'">
                      ${ col.value ? 'Required' : 'Open' }
                    </q-badge>
                  </div>
                  <div v-else>${ col.value }</div>
                </q-td>
              </q-tr>
            </template>
          </q-table>
        </q-card-section>
      </q-card>
    </div>

    <!-- ═══════════════════════════════ RIGHT COLUMN ═════════════════════════ -->
    <div class="col-12 col-md-4 col-lg-3 q-gutter-y-md">
      <q-card>
        <q-card-section>
          <h6 class="text-subtitle1 q-my-none">files4sats</h6>
          <p class="q-mt-sm">
            Sell digital files via Lightning. Upload a file, set a price, and
            share the public link (and optionally the integrity code) with your buyer.
          </p>
        </q-card-section>
        <q-separator></q-separator>
        <q-card-section class="q-pa-none">
          <q-list>
            <q-expansion-item group="extras" icon="info" label="How it works">
              <q-card>
                <q-card-section class="q-gutter-y-sm">
                  <p><strong>1. Create a product</strong> — upload your file and set a price in sats.</p>
                  <p><strong>2. Share</strong> the public link <em>and</em> the SHA-256 hash privately with your buyer.</p>
                  <p><strong>3. Buyer validates</strong> the hash, pays the invoice, and downloads.</p>
                  <p><strong>4. File stays protected</strong> — never accessible without a confirmed payment.</p>
                </q-card-section>
              </q-card>
            </q-expansion-item>
          </q-list>
        </q-card-section>
      </q-card>
    </div>

    <!-- ══════════════════════════ CREATE PRODUCT DIALOG ════════════════════ -->
    <q-dialog v-model="productDialog.show" position="top">
      <q-card v-if="productDialog.show" class="q-pa-lg q-pt-md lnbits__dialog-card" style="min-width: 480px">
        <span class="text-h5 q-mb-md block">New Product</span>

        <q-input filled dense v-model.trim="productDialog.data.name"
          label="Product name *" class="q-mb-sm"></q-input>

        <q-input filled dense v-model="productDialog.data.description"
          label="Description" type="textarea" rows="2" class="q-mb-sm"></q-input>

        <q-input filled dense v-model.number="productDialog.data.price_sats"
          label="Price (sats) *" type="number" min="1" class="q-mb-sm"></q-input>

        <q-select filled dense emit-value map-options
          v-model="productDialog.data.wallet_id"
          :options="g.user.walletOptions"
          label="Receive wallet *" class="q-mb-sm">
        </q-select>

        <q-checkbox v-model="productDialog.data.require_integrity"
          label="Require integrity code validation before payment" class="q-mb-md">
        </q-checkbox>

        <!-- File picker -->
        <q-file filled dense
          v-model="productDialog.data.file"
          label="File to sell *"
          class="q-mb-md"
          accept="*/*"
          :max-file-size="1073741824"
          hint="Any file type. Maximum 1 GB."
          @update:model-value="onFileSelected"
        >
          <template v-slot:prepend><q-icon name="attach_file"></q-icon></template>
        </q-file>

        <div class="row q-mt-md">
          <q-btn @click="saveProduct" unelevated color="primary" :loading="productDialog.loading">
            Create &amp; Upload
          </q-btn>
          <q-btn v-close-popup flat color="grey" class="q-ml-auto">Cancel</q-btn>
        </div>
      </q-card>
    </q-dialog>

    <!-- ══════════════════════════ HASH REVEAL DIALOG ════════════════════════ -->
    <q-dialog v-model="hashDialog.show" persistent>
      <q-card class="q-pa-lg" style="min-width: 500px; max-width: 90vw">
        <q-card-section>
          <div class="text-h6 q-mb-xs">Product created!</div>
          <div class="text-subtitle2 text-grey q-mb-md">${ hashDialog.productName }</div>

          <q-banner class="bg-teal-1 text-teal-9 q-mb-md" rounded>
            <template v-slot:avatar><q-icon name="security" color="teal"></q-icon></template>
            Share both the <strong>SHA-256 hash</strong> and the <strong>public link</strong>
            privately with your buyer. The hash is used to unlock the payment.
          </q-banner>

          <div class="text-overline text-grey q-mb-xs">SHA-256 Integrity Hash</div>
          <div class="row items-center q-mb-md">
            <code class="col q-pa-sm bg-grey-2 rounded-borders" style="word-break:break-all;font-size:0.75rem">
              ${ hashDialog.hash }
            </code>
            <q-btn flat round dense icon="content_copy" class="q-ml-sm"
              @click="copyHash" :color="hashDialog.copied ? 'positive' : 'grey'">
              <q-tooltip>${ hashDialog.copied ? 'Copied!' : 'Copy hash' }</q-tooltip>
            </q-btn>
          </div>

          <div class="text-overline text-grey q-mb-xs">Public buyer link</div>
          <div class="row items-center">
            <code class="col q-pa-sm bg-grey-2 rounded-borders" style="word-break:break-all;font-size:0.75rem">
              ${ hashDialog.shareLink }
            </code>
            <q-btn flat round dense icon="content_copy" class="q-ml-sm" color="grey"
              @click="copyShareLink">
              <q-tooltip>Copy link</q-tooltip>
            </q-btn>
          </div>
        </q-card-section>

        <q-card-actions align="right">
          <q-btn flat label="Close" v-close-popup color="primary"></q-btn>
        </q-card-actions>
      </q-card>
    </q-dialog>

  </div>
</template>