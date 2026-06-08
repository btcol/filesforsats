<!------------------------------------------------------------------->
<!-- USER FACING PUBLIC PAGE                                       -->
<!------------------------------------------------------------------->

<template id="page-filesforsats-public">
  <div class="row q-col-gutter-md justify-center q-pt-lg">
    <!-- ── Loading ────────────────────────────────────────────────── -->
    <div v-if="step === 'loading'" class="col-12 text-center q-mt-xl">
      <q-spinner-orbit color="primary" size="4em"></q-spinner-orbit>
      <p class="q-mt-md text-grey">Loading product…</p>
    </div>

    <!-- ── Error ──────────────────────────────────────────────────── -->
    <div v-else-if="step === 'error'" class="col-12 col-sm-8 col-md-5">
      <q-card class="q-pa-lg text-center">
        <q-icon
          name="error_outline"
          size="4em"
          color="negative"
          class="q-mb-md"
        ></q-icon>
        <p>Product not found or is no longer available.</p>
      </q-card>
    </div>

    <!-- ── Main flow ───────────────────────────────────────────────── -->
    <template v-else-if="product">
      <!-- Left: product info -->
      <div class="col-12 col-sm-10 col-md-5 col-lg-4 q-gutter-y-md">
        <!-- Product card -->
        <q-card class="q-pa-md">
          <q-card-section class="q-pa-none q-mb-sm">
            <div class="text-h6">${ product.name }</div>
            <div class="text-caption text-grey">
              ${ product.file_name } · ${ fileSizeFormatted } · ${
              product.mime_type }
            </div>
          </q-card-section>
          <q-card-section class="q-pa-none q-mb-md" v-if="product.description">
            <p class="q-my-none">${ product.description }</p>
          </q-card-section>
          <q-separator class="q-mb-md"></q-separator>
          <div class="row items-center">
            <q-icon name="bolt" color="amber" size="1.4em"></q-icon>
            <span class="text-h5 text-bold q-ml-xs">${ priceFormatted }</span>
          </div>
        </q-card>

        <!-- ── STEP: Integrity required ──────────────────────────── -->
        <q-card v-if="step === 'integrity_required'" class="q-pa-md">
          <q-card-section class="q-pa-none">
            <div class="text-subtitle2 q-mb-xs">
              <q-icon name="security" color="teal" class="q-mr-xs"></q-icon>
              Integrity code required
            </div>
            <p class="text-caption text-grey q-mb-md">
              The seller shared a unique integrity code with you privately.
              Enter it below to unlock the payment.
            </p>
            <q-input
              filled
              dense
              v-model.trim="integrityCode"
              label="Integrity code"
              placeholder="Paste the SHA-256 hash here"
              :error="!!integrityError"
              :error-message="integrityError"
              @keyup.enter="submitIntegrity"
            ></q-input>
          </q-card-section>
          <q-card-actions class="q-pa-none q-mt-md">
            <q-btn
              @click="submitIntegrity"
              unelevated
              color="teal"
              :loading="integrityLoading"
              class="full-width"
            >
              Validate
            </q-btn>
          </q-card-actions>
        </q-card>

        <!-- ── STEP: Integrity validated → show invoice button ───── -->
        <q-card v-else-if="step === 'integrity_ok'" class="q-pa-md">
          <q-card-section class="q-pa-none q-mb-md">
            <q-banner rounded class="bg-teal-1 text-teal-9">
              <template v-slot:avatar
                ><q-icon name="check_circle" color="teal"></q-icon
              ></template>
              Integrity code validated. You can now proceed to payment.
            </q-banner>
          </q-card-section>
          <q-btn
            @click="createInvoice"
            unelevated
            color="primary"
            icon="bolt"
            :loading="invoiceLoading"
            class="full-width"
          >
            Pay ${ priceFormatted }
          </q-btn>
        </q-card>

        <!-- ── STEP: No integrity required → direct invoice ──────── -->
        <q-card v-else-if="step === 'ready_for_invoice'" class="q-pa-md">
          <q-btn
            @click="createInvoice"
            unelevated
            color="primary"
            icon="bolt"
            :loading="invoiceLoading"
            class="full-width"
          >
            Pay ${ priceFormatted }
          </q-btn>
        </q-card>

        <!-- ── STEP: Awaiting payment (QR + status) ──────────────── -->
        <q-card
          v-else-if="step === 'awaiting_payment'"
          class="q-pa-md text-center"
        >
          <q-card-section class="q-pa-none q-mb-sm">
            <div class="text-subtitle2 q-mb-md">
              Scan or paste into your Lightning wallet
            </div>
            <lnbits-qrcode
              :href="'lightning:' + paymentRequest"
              :value="'lightning:' + paymentRequest"
            ></lnbits-qrcode>
          </q-card-section>
          <q-card-section class="q-pa-none">
            <q-input
              filled
              dense
              readonly
              :value="paymentRequest"
              label="Invoice"
            >
              <template v-slot:append>
                <q-btn
                  flat
                  dense
                  icon="content_copy"
                  @click="
                    () => {
                      navigator.clipboard.writeText(paymentRequest)
                      Quasar.Notify.create({
                        type: 'positive',
                        message: 'Copied!'
                      })
                    }
                  "
                >
                </q-btn>
              </template>
            </q-input>
          </q-card-section>
          <div class="q-mt-md text-grey text-caption">
            <q-spinner-dots
              color="primary"
              size="1.2em"
              class="q-mr-xs"
            ></q-spinner-dots>
            Waiting for payment confirmation…
          </div>
        </q-card>

        <!-- ── STEP: Paid — download ready ───────────────────────── -->
        <q-card v-else-if="step === 'paid'" class="q-pa-md text-center">
          <q-icon
            name="check_circle"
            color="positive"
            size="4em"
            class="q-mb-sm"
          ></q-icon>
          <div class="text-h6 q-mb-sm">Payment confirmed!</div>
          <div class="text-caption text-grey q-mb-lg">
            Your file is ready to download.
          </div>
          <q-btn
            @click="downloadFile"
            unelevated
            color="positive"
            icon="download"
            size="lg"
            class="full-width"
          >
            Download ${ product.file_name }
          </q-btn>
        </q-card>
      </div>
    </template>
  </div>
</template>
