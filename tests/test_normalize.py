#test per il file normalizer.py
from app.services.normalize import (
    contract_type_norm, 
    work_mode, 
    country_code,
    city,
    salary,
    years_experience,
)

def test_contratto_tempo_indeterminato_italiano():
    result = contract_type_norm ("Contratto a tempo indeterminato")
    assert result == "full_time"

def test_BUG_permanent_contract_inglese():
    result = contract_type_norm("Permanent contract, full time")
    assert result == "contract" 
    
def test_stage():
    assert contract_type_norm("Stage curriculare") == "intership"
        
def test_BUG_permanent_contract():
    assert contract_type_norm("Permanent contract, full time") == "contract"
    
def test_nessun_contratto():
    assert contract_type_norm("") is None
    assert contract_type_norm(None) is None
    
    
    
    
    
def test_remote():
    assert work_mode("Posizione fully remote") == "remote"
    
def test_hybrid():
    assert work_mode("Lavoro ibrido, 2 giorni in ufficio") == "hybrid"

def test_BUG_not_remote():
    assert work_mode("This role is not remote") == "remote"
    
def test_onsite():
    assert work_mode("Posizione in sede, presenza obbligatoria") == "onsite"
    
                        
def test_BUG_ragusa_letta_come_stati_uniti():
    result = country_code ("Ragusa, Sicilia, Italia")
    assert result == "IT"  
    
def test_citta_semplice():
    result = city("Milano, Lombardia, Italia")
    assert result == "Milano"

def test_italia_dalla_citta():
    assert country_code("Civitanova Marche, Marche") == "IT"

def test_germania():
    assert country_code("Berlin, Deutschland") == "DE"
    
def test_sconosciuta():
    assert country_code("Ubicazione sconosciuta xyz") is None

def test_nessuna_sede():
    assert country_code(None) is None    








def test_city_prima_virgola():
    assert city("Milano, Lombardia, Italia") == "Milano"

def test_city_senza_virgola():
    result = city("Remote")
    assert result == "Remote"

def test_city_none():
    assert city(None) is None
    
    
    
def test_stipendio_orario_scambiato_per_annuo():
    lo, hi, cur = salary("20 - 30 EUR per hour")
    assert (lo, hi, cur) == (20000, 30000, "EUR")  

def test_stipendio_euro():
    lo, hi, cur = salary("RAL 30.000 - 40.000 EUR")
    assert lo == 30000 and hi == 40000 and cur == "EUR"

def test_notazione_k():
    lo, hi, cur = salary("45k - 60k EUR")
    assert lo == 45000 and hi == 60000 and cur == "EUR"
    
def test_nessuno_stipendio():
    lo, hi, cur = salary("Stipendio da concordare")
    assert lo is None and hi is None and cur is None    
    
      
  
def test_range_anni():
    lo, hi = years_experience("Richiesti 3-5 anni di esperienza")
    assert lo == 3 and hi == 5

def test_minimo_anni():
    lo, hi = years_experience("Almeno 2 anni di esperienza")
    assert lo == 2 and hi is None

def test_nessun_anno():
    lo, hi = years_experience("Posizione entry level")
    assert lo is None and hi is None  