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
          <h6 class="text-subtitle1 q-my-none">filesforsats</h6>
          <p class="q-mt-sm">
            Sell digital files via Lightning. Upload a file, set a price, and
            share the public link (and optionally the integrity code) with your buyer.
          </p>
          <!-- Commission info banner for sellers -->
          <q-banner v-if="adminSettings.commission_percent > 0" class="bg-orange-1 text-orange-9 q-mt-sm" rounded dense>
            <template v-slot:avatar><q-icon name="info" color="orange" /></template>
            A <strong>${ adminSettings.commission_percent }%</strong> platform commission
            is automatically deducted from each sale.
          </q-banner>
          <!-- Storage Quota UI -->
          <div class="q-mt-md">
            <div class="row items-center justify-between q-mb-xs">
              <span class="text-caption text-weight-medium">Storage Quota</span>
              <span class="text-caption text-grey-8">${ formattedStorageUsage }</span>
            </div>
            <q-linear-progress 
              :value="storageProgress" 
              :color="storageProgress >= 0.9 ? 'negative' : (storageProgress >= 0.75 ? 'warning' : 'primary')"
              rounded
              size="10px"
              class="q-mt-sm"
            />
          </div>
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

      <!-- ═══════════════════════ ABOUT BUTTON ══════════════════════════ -->
      <q-card class="q-mt-md">
        <q-card-section>
          <q-btn
            outline color="primary" icon="info"
            label="About this App" class="full-width"
            @click="showAboutDialog"
          />
        </q-card-section>
      </q-card>

      <!-- ═══════════ ADMIN SETTINGS BUTTON (superuser only) ═════════════ -->
      <q-card v-if="g.user.admin" class="q-mt-md">
        <q-card-section>
          <q-btn
            unelevated color="primary" icon="admin_panel_settings"
            label="Admin Settings" class="full-width"
            @click="adminDialog = true"
          />
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

    <!-- ══════════════════════ ADMIN SETTINGS DIALOG ══════════════════════ -->
    <q-dialog v-model="adminDialog" position="top">
      <q-card class="q-pa-lg q-pt-md lnbits__dialog-card" style="min-width: 480px">
        <span class="text-h5 q-mb-md block">Admin Settings</span>

        <q-card-section class="q-pa-none q-gutter-y-md">
          <q-input filled dense v-model.number="adminForm.commission_percent"
            label="Commission % per sale" type="number" min="0" max="100" step="0.01">
            <template v-slot:append>
              <q-icon name="help_outline" class="cursor-pointer">
                <q-tooltip>Set to 0 to disable. This percentage is automatically deducted from each sale and sent to the commission wallet.</q-tooltip>
              </q-icon>
            </template>
          </q-input>

          <q-select filled dense emit-value map-options
            v-model="adminForm.commission_wallet_id"
            :options="g.user.walletOptions"
            label="Commission wallet" />

          <q-input filled dense v-model.number="adminForm.storage_quota_mb"
            label="Storage quota per user (MB)" type="number" min="1" step="1">
            <template v-slot:append>
              <q-icon name="help_outline" class="cursor-pointer">
                <q-tooltip>Maximum storage space allowed per user in megabytes. Default is 1024 MB (1 GB).</q-tooltip>
              </q-icon>
            </template>
          </q-input>

          <div>
            <q-toggle v-model="adminForm.unlock_monthly" color="orange"
              :label="adminForm.unlock_monthly ? 'Unlock: Monthly renewal' : 'Unlock: One-time payment'">
              <q-tooltip>OFF = sellers pay once forever. ON = sellers must renew every month.</q-tooltip>
            </q-toggle>
          </div>
        </q-card-section>

        <div class="row q-mt-lg">
          <q-btn @click="saveAdminSettings" unelevated color="primary"
            :loading="adminForm.loading">Save</q-btn>
          <q-btn v-close-popup flat color="grey" class="q-ml-auto">Cancel</q-btn>
        </div>
      </q-card>
    </q-dialog>

    <!-- ════════════════════════ ABOUT APP DIALOG ═══════════════════════ -->
    <q-dialog v-model="aboutDialog.show" position="top">
      <q-card class="q-pa-lg q-pt-md lnbits__dialog-card" style="min-width: 480px" v-if="aboutDialog.config">
        <span class="text-h5 q-mb-md block">${aboutDialog.config.name} <span class="text-caption text-grey">v${aboutDialog.config.version}</span></span>

        <q-card-section class="q-pa-none q-gutter-y-md">
          <p class="text-body2 text-grey-8">${aboutDialog.config.short_description}</p>
          
          <div v-if="aboutDialog.config.images && aboutDialog.config.images.length > 0">
            <div v-if="aboutDialog.config.images[0].uri" class="q-mb-md text-center">
              <img :src="aboutDialog.config.images[0].uri" style="max-width: 100%; max-height: 200px; object-fit: contain; border-radius: 4px;" />
            </div>
            
            <a v-if="aboutDialog.config.images[0].link" :href="aboutDialog.config.images[0].link" target="_blank" style="text-decoration: none;">
              <q-btn outline color="red" icon="play_circle" label="Watch Video Tutorial" class="full-width" />
            </a>
          </div>

          <div v-if="aboutDialog.config.contributors && aboutDialog.config.contributors.length > 0">
            <p class="text-subtitle2 q-mt-md q-mb-xs">Developed by:</p>
            <q-list dense>
              <q-item v-for="c in aboutDialog.config.contributors" :key="c.name" :href="c.uri" tag="a" target="_blank" clickable>
                <q-item-section avatar>
                  <q-icon name="code" />
                </q-item-section>
                <q-item-section>
                  <q-item-label>${c.name}</q-item-label>
                  <q-item-label caption>${c.role}</q-item-label>
                </q-item-section>
              </q-item>
            </q-list>
          </div>
        </q-card-section>

        <div class="row q-mt-lg justify-end">
          <q-btn v-close-popup flat color="primary">Close</q-btn>
        </div>
      </q-card>
    </q-dialog>

  </div>
</template>