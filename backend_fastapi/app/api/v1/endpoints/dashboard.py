"""Laporan ringkas untuk kartu dashboard."""
from fastapi import APIRouter, Depends

from app.api import deps
from app.services.dashboard_report_service import dashboard_report

router = APIRouter()


@router.get(
    "/laporan",
    summary="Laporan dashboard: produksi TBS, yield, status tanam, dan rotasi",
    description="Satu respons dengan empat kueri terpisah. Superadmin mendapat seluruh data. "
                "Role lain hanya blok pada hak akses wilayahnya, dan tema tanpa hak transaksi dikembalikan "
                "dengan akses=false tanpa angka.",
)
def get_dashboard_report(db=Depends(deps.get_db), current_user=Depends(deps.get_current_user)):
    return dashboard_report(db, current_user)
