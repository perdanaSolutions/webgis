"""Probe identitas sertifikat klien. Tidak memakai sesi pengguna."""
from fastapi import APIRouter, Depends

from app.core.mtls import verify_client_certificate

router = APIRouter()


@router.get("/identity", summary="Identitas sertifikat klien mTLS (CN backend-external)")
def mtls_identity(client_cn: str = Depends(verify_client_certificate)):
    return {"status": "success", "authorized_client": client_cn}
