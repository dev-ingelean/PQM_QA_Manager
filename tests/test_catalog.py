from pqm_quality_manager.config.evidence_catalog import EVIDENCE_CATALOG

def test_catalog_is_unique_and_has_expected_are_codes():
    assert len(EVIDENCE_CATALOG)==35
    codes=[item.code for item in EVIDENCE_CATALOG]
    assert len(codes)==len(set(codes))
    assert codes[0]=="ALIM-UPS-IN"
    assert codes[-1]=="SO-ALMACENAMIENTO"
    assert [e.order for e in EVIDENCE_CATALOG]==list(range(1,36))
