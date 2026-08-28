"""
Router: geografia della ricerca.

Espone l'albero continente > stato > regione al frontend, che lo usa per
popolare i due menu a tendina. Un solo endpoint di lettura: i dati sono
statici e non c'è niente da scrivere.
"""
from fastapi import APIRouter, Depends
from app.services import geo
from app.core.security import verify_token
router = APIRouter(prefix="/api/geo", tags=["Geografia"], dependencies=[Depends(verify_token)],)


@router.get("")
def geo_tree() -> dict:
    """Continenti, stati e loro regioni.

    Il frontend se lo carica una volta all'avvio: scegliendo un continente
    il campo Zona si disabilita (un continente non ha regioni), scegliendo
    uno stato si popola con le sue."""
    return geo.tree()
