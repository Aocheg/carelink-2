from datetime import date, datetime, timezone
from typing import Literal, Optional
from pydantic import BaseModel, Field, model_validator


class Input(BaseModel):
    model_config = {"extra": "forbid"}


class PatientIn(Input):
    full_name: str = Field(min_length=2, max_length=160)
    date_of_birth: date
    sex: str
    marital_status: Optional[str] = None; religion: Optional[str] = None; occupation: Optional[str] = None
    address: Optional[str] = None; phone_number: Optional[str] = None; blood_group: Optional[str] = None; genotype: Optional[str] = None
    allergy_status: bool = False; allergy_details: Optional[str] = None

    @model_validator(mode="after")
    def allergy_consistency(self):
        if self.allergy_status != bool(self.allergy_details): raise ValueError("allergy status and details must agree")
        return self

class FreshAdmissionIn(Input):
    full_name: str = Field(min_length=2, max_length=160)
    date_of_birth: date
    sex: str
    phone_number: Optional[str] = None
    address: Optional[str] = None
    blood_group: Optional[str] = None
    genotype: Optional[str] = None
    allergy_status: bool = False
    allergy_details: Optional[str] = None
    ward_id: int
    bed_id: int
    admitted_by: int
    source: str
    reason_for_admission: str

    @model_validator(mode="after")
    def allergy_consistency(self):
        if self.allergy_status != bool(self.allergy_details):
            raise ValueError("allergy status and details must agree")
        return self

class UserIn(Input): username: str; password: str = Field(min_length=8); full_name: str; role: str = "NURSE"
class FacilityIn(Input): name: str; description: Optional[str] = None
class WardIn(Input): facility_id: int; name: str
class BedIn(Input): ward_id: int; bed_number: str
class KinIn(Input): full_name: str; relationship: str; phone_number: str; address: Optional[str] = None; is_primary: bool = False

class AdmissionIn(Input):
    patient_id: int; ward_id: int; bed_id: int; admitted_by: int; source: str; reason_for_admission: str
    presenting_complaint: Optional[str] = None; patient_account: Optional[str] = None; doctor_assessment: Optional[str] = None; nursing_assessment: Optional[str] = None; nursing_diagnosis: Optional[str] = None

class VitalIn(Input):
    recorded_by: int; recorded_at: datetime; systolic_bp: Optional[int] = Field(None, ge=40, le=300); diastolic_bp: Optional[int] = Field(None, ge=20, le=200)
    pulse: Optional[int] = Field(None, ge=20, le=300); temperature: Optional[float] = Field(None, ge=25, le=45); respiratory_rate: Optional[int] = Field(None, ge=4, le=80); spo2: Optional[float] = Field(None, ge=0, le=100)
    measurement_status: Literal["COMPLETE", "PARTIAL", "NOT_MEASURED"]; not_measured_reason: Optional[str] = None; notes: Optional[str] = None
    @model_validator(mode="after")
    def validate_measurement(self):
        vals = [self.systolic_bp, self.diastolic_bp, self.pulse, self.temperature, self.respiratory_rate, self.spo2]
        if (self.systolic_bp is None) != (self.diastolic_bp is None): raise ValueError("blood pressure must be paired")
        n = sum(v is not None for v in vals)
        if self.measurement_status == "COMPLETE" and (n != 6 or self.not_measured_reason): raise ValueError("COMPLETE requires every value and no reason")
        if self.measurement_status == "PARTIAL" and (n == 0 or n == 6 or not self.not_measured_reason): raise ValueError("PARTIAL requires some values and a reason")
        if self.measurement_status == "NOT_MEASURED" and (n or not self.not_measured_reason): raise ValueError("NOT_MEASURED requires no values and a reason")
        if self.recorded_at.tzinfo is None: raise ValueError("recorded_at must be timezone-aware")
        self.recorded_at = self.recorded_at.astimezone(timezone.utc); return self

class MedicationOrderIn(Input):
    medication_name: str; dose: str; route: str; frequency: str; start_date: date; end_date: Optional[date] = None; prescribed_by: int; instructions: Optional[str] = None
    @model_validator(mode="after")
    def dates(self):
        if self.end_date and self.end_date < self.start_date: raise ValueError("end_date cannot precede start_date")
        return self
class AdministrationIn(Input):
    administered_by: int; administered_at: datetime; status: Literal["ADMINISTERED", "NOT_ADMINISTERED", "REFUSED", "HELD"]; not_administered_reason: Optional[str] = None; notes: Optional[str] = None
    @model_validator(mode="after")
    def administration(self):
        if self.administered_at.tzinfo is None: raise ValueError("administered_at must be timezone-aware")
        if (self.status == "ADMINISTERED") == bool(self.not_administered_reason): raise ValueError("reason is required only when not administered")
        self.administered_at = self.administered_at.astimezone(timezone.utc); return self

class InvestigationIn(Input): requested_by: int; tests: list[str] = Field(min_length=1); clinical_notes: Optional[str] = None
class ResultIn(Input): result_value: str; result_notes: Optional[str] = None; is_critical: bool = False
class ReviewIn(Input): reviewed_by: int; reviewed_at: datetime; assessment: str; plan: Optional[str] = None
class ClinicalOrderIn(Input): ordered_by: int; order_type: str; details: str
class HandoverIn(Input): sent_by: int; received_by: Optional[int] = None; shift: str; current_condition: str; recent_observations: Optional[str] = None; outstanding_issues: Optional[str] = None; risks: Optional[str] = None; nursing_notes: Optional[str] = None
class AlertIn(Input): alert_type: str; severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]; message: str
class ActorIn(Input): actor_id: int
class DischargeIn(Input): discharged_by: int; discharged_at: datetime; discharge_status: str; discharge_summary: str; diagnosis_outcome: Optional[str] = None; medications_instructions: Optional[str] = None; follow_up: Optional[str] = None


class LoginIn(Input):
    username: str
    password: str

class StatusTransitionIn(Input):
    status: str

class ClinicalOrderStatusIn(Input):
    status: Literal["ACTIVE", "COMPLETED", "CANCELLED"]

class InvestigationStatusIn(Input):
    actor_id: int

class BootstrapIn(Input):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=2, max_length=160)
