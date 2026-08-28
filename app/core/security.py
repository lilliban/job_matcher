"""
Sicurezza — autenticazione via token.

L'app è locale, quindi non serve un sistema complesso di utenti/password.
Basta un token condiviso che il frontend manda in ogni richiesta.

Se l'app viene esposta in rete, sostituire con OAuth2/JWT.
"""
import os
from fastapi import Header, HTTPException, Depends

from app.core.config import API_TOKEN


async def verify_token(x_api_token: str | None = Header(default=None)) -> None:
    """Verifica che il token nell'header sia valido.

    Chiamata come dependency nei router.
    """
    if not API_TOKEN:
        # Se non c'è token configurato, non proteggere (modalità dev)
        return None
    
    if x_api_token != API_TOKEN:
        raise HTTPException(
            status_code=401,
            detail="Token non valido. Aggiungi header 'X-API-Token'.",
        )
    
    return None