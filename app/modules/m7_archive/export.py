from fastapi.responses import JSONResponse


def evidence(ledger, ident):
    source, snapshot = ledger.read(ident)
    return JSONResponse({**snapshot, "source": source}, headers={
        "Content-Disposition": f'attachment; filename="evidence-{ident[:12]}.json"',
        "Cache-Control": "private, no-store",
    })
