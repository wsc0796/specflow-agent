"""Fictional API v2; read as source only, never execute."""

from fastapi import FastAPI, HTTPException

app = FastAPI()
jobs = {}


@app.post("/exports", status_code=201)
def create_export():
    return {"job_id": "job-example"}


@app.post("/exports/{job_id}/cancel")
def cancel_export(job_id: str):
    job = jobs[job_id]
    if job["state"] == "running":
        raise HTTPException(status_code=409, detail="JOB_NOT_CANCELLABLE")
    job["state"] = "cancelled"
    return {"job_id": job_id, "state": "cancelled"}
