<script setup lang="ts">
import { computed, ref } from "vue";
import {
  useDocumentUploadStore,
  type SampleAnalysis,
  type ThemeColumn,
} from "~/stores/documentUploadStore";
import { getErrorMessage } from "~/utils/getErrorMessage";

const emit = defineEmits<{ (e: "close"): void; (e: "created", kode: string): void }>();

const store = useDocumentUploadStore();
const fileInputRef = ref<HTMLInputElement | null>(null);

const columnTypes = ["text", "integer", "float", "boolean", "date"] as const;

const sampleName = ref("");
const analysis = ref<SampleAnalysis | null>(null);
const columns = ref<ThemeColumn[]>([]);
const kode = ref("");
const nama = ref("");
const deskripsi = ref("");
const relasiBlok = ref(true);
const isBusy = ref(false);
const errorMessage = ref("");

const canSubmit = computed(
  () =>
    Boolean(analysis.value) &&
    kode.value.trim() !== "" &&
    nama.value.trim() !== "" &&
    columns.value.length > 0 &&
    columns.value.every((col) => col.nama_kolom.trim() !== "") &&
    !isBusy.value,
);

async function onSampleChange(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0];
  if (!file) return;
  errorMessage.value = "";
  isBusy.value = true;
  try {
    const result = await store.analyzeSample(file);
    analysis.value = result;
    columns.value = result.kolom.map((col) => ({ ...col }));
    sampleName.value = file.name;
  } catch (error) {
    analysis.value = null;
    columns.value = [];
    errorMessage.value = getErrorMessage(error, "Analisis file contoh gagal.");
  } finally {
    isBusy.value = false;
  }
}

function removeColumn(index: number) {
  columns.value.splice(index, 1);
}

async function submit() {
  if (!analysis.value || !canSubmit.value) return;
  errorMessage.value = "";
  isBusy.value = true;
  try {
    const created = await store.createTheme({
      kode: kode.value.trim(),
      nama: nama.value.trim(),
      deskripsi: deskripsi.value.trim() || null,
      geometry_type: analysis.value.geometry_type,
      relasi_blok: relasiBlok.value,
      kolom: columns.value,
    });
    emit("created", created.kode);
    emit("close");
  } catch (error) {
    errorMessage.value = getErrorMessage(error, "Gagal membuat tema baru.");
  } finally {
    isBusy.value = false;
  }
}
</script>

<template>
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-overlay-dark p-4">
    <div class="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-xl bg-surface p-6 shadow-2xl">
      <h3 class="text-18 font-bold text-brand">Buat Tema Baru</h3>
      <p class="mt-1 text-size-sm text-muted">
        Upload file GeoJSON contoh. Skema kolom disarankan otomatis dan bisa Anda sesuaikan sebelum tema dibuat.
      </p>

      <div class="mt-4">
        <input ref="fileInputRef" type="file" accept=".geojson,.json" class="hidden" @change="onSampleChange" />
        <button type="button"
          class="rounded-xl bg-brand px-4 py-2 font-semibold text-on-brand disabled:opacity-50"
          :disabled="isBusy" @click="fileInputRef?.click()">
          {{ analysis ? "Ganti File Contoh" : "Pilih File Contoh" }}
        </button>
        <span v-if="sampleName" class="ml-3 text-size-sm text-label">{{ sampleName }}</span>
      </div>

      <template v-if="analysis">
        <p class="mt-3 text-size-sm text-label">
          Geometry: <span class="font-semibold">{{ analysis.geometry_type }}</span> ·
          {{ analysis.jumlah_data_dianalisis.toLocaleString("id-ID") }} dari
          {{ analysis.jumlah_data_total_di_file.toLocaleString("id-ID") }} data dianalisis
        </p>

        <div class="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
          <div>
            <label class="mb-1 block text-label font-medium">Kode</label>
            <input v-model="kode" type="text" placeholder="mis. embung"
              class="w-full rounded-xl border border-default px-3 py-2 text-size-sm" />
          </div>
          <div>
            <label class="mb-1 block text-label font-medium">Nama</label>
            <input v-model="nama" type="text" placeholder="mis. Embung"
              class="w-full rounded-xl border border-default px-3 py-2 text-size-sm" />
          </div>
          <div class="md:col-span-2">
            <label class="mb-1 block text-label font-medium">Deskripsi</label>
            <input v-model="deskripsi" type="text"
              class="w-full rounded-xl border border-default px-3 py-2 text-size-sm" />
          </div>
          <label class="flex items-center gap-2 text-size-sm text-label md:col-span-2">
            <input v-model="relasiBlok" type="checkbox" />
            Data terikat ke blok (hierarki kebun)
          </label>
        </div>

        <div class="mt-4 overflow-x-auto rounded-xl border border-default">
          <table class="min-w-full bg-surface text-size-sm">
            <thead class="bg-surface-warm text-left text-brand">
              <tr>
                <th class="px-3 py-2 font-bold">Properti di File</th>
                <th class="px-3 py-2 font-bold">Nama Kolom</th>
                <th class="px-3 py-2 font-bold">Tipe</th>
                <th class="px-3 py-2 font-bold">Boleh Kosong</th>
                <th class="px-3 py-2" />
              </tr>
            </thead>
            <tbody>
              <tr v-for="(col, index) in columns" :key="col.nama_properti" class="border-t border-row">
                <td class="px-3 py-2">{{ col.nama_properti }}</td>
                <td class="px-3 py-2">
                  <input v-model="col.nama_kolom" type="text"
                    class="w-full rounded-lg border border-default px-2 py-1" />
                </td>
                <td class="px-3 py-2">
                  <select v-model="col.tipe" class="rounded-lg border border-default px-2 py-1">
                    <option v-for="type in columnTypes" :key="type" :value="type">{{ type }}</option>
                  </select>
                </td>
                <td class="px-3 py-2"><input v-model="col.nullable" type="checkbox" /></td>
                <td class="px-3 py-2">
                  <button type="button" class="text-error" @click="removeColumn(index)">Hapus</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>

      <p v-if="errorMessage" class="mt-4 rounded-xl bg-error-light px-4 py-3 text-error">{{ errorMessage }}</p>

      <div class="mt-5 flex justify-end gap-2">
        <button type="button" class="rounded-xl border border-tan bg-cream px-4 py-2 font-semibold text-brand"
          :disabled="isBusy" @click="emit('close')">
          Batal
        </button>
        <button type="button"
          class="rounded-xl bg-brand px-4 py-2 font-semibold text-on-brand disabled:opacity-50"
          :disabled="!canSubmit" @click="submit">
          {{ isBusy ? "Memproses..." : "Buat Tema" }}
        </button>
      </div>
    </div>
  </div>
</template>
