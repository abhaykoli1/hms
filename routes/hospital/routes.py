from fastapi import APIRouter, HTTPException
from typing import List

from models import HospitalModel
from routes.auth.schemas import HospitalCreate, HospitalResponse


router = APIRouter(prefix="/hospital", tags=["Hospital"])

@router.post("/create", response_model=HospitalResponse)
def create_hospital(payload: HospitalCreate):
    hospital = HospitalModel(**payload.dict()).save()

    return {
        "id": str(hospital.id),
        **payload.dict()
    }

@router.get("/get-all", response_model=List[HospitalResponse])
def get_hospitals():
    hospitals = HospitalModel.objects()

    return [
        {
            "id": str(h.id),
            "name": h.name,
            "address": h.address,
            "branch": h.branch
        }
        for h in hospitals
    ]
