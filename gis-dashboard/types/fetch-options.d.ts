// Opsi tambahan untuk $api: matikan redirect /maintenance saat 5xx (error ditangani inline).
declare module "ofetch" {
  interface FetchOptions {
    skipServerErrorRedirect?: boolean;
  }
}
export {};
