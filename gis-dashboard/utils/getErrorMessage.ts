export const getErrorMessage = (
  error: any,
  fallbackMessage: string = "Terjadi kesalahan. Silakan coba lagi.",
): string => {
  // 1. Cek apakah format error sesuai dengan array dari backend
  if (error?.data?.errors && Array.isArray(error.data.errors)) {
    const backendErrors = error.data.errors;
    const errorMessages: string[] = [];

    backendErrors.forEach((err: { field: string; msg: string }) => {
      if (err.field) {
        // Format string per field, contoh "username: Field required"
        errorMessages.push(`${err.field}: ${err.msg}`);
      }
    });

    // 2. Gabungkan semua pesan dengan tanda koma jika ada error yang valid
    if (errorMessages.length > 0) {
      return errorMessages.join(", ");
    }
  } else if (
    typeof error.data.errors === "string" ||
    typeof error.data.detail === "string"
  ) {
    return error.data.errors || error.data.detail;
  } else {
    return fallbackMessage;
  }

  // 3. Fallback jika format error berbeda (misal error detail biasa atau network error)
  return error?.data?.detail || error?.message || fallbackMessage;
};
