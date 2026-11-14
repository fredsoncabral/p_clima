import re

from p_clima.inmet.bdmep import COLUNAS_BDMEP, REGEX_ARQUIVO, REGEX_DATA


def test_regex_nome_arquivo():
    m = re.match(REGEX_ARQUIVO, "INMET_CO_DF_A045_AGUAS EMENDADAS_01-01-2024_A_31-12-2024.CSV")
    assert m.groups() == ("CO", "DF", "A045", "AGUAS EMENDADAS", "01-01-2024", "31-12-2024")
    assert re.match(REGEX_ARQUIVO, "INMET_NE_BA_A472_ACAJUTIBA_08-05-2026_A_31-10-2026.csv")


def test_regex_data_aceita_formatos_antigo_e_novo():
    assert re.match(REGEX_DATA, "2024/01/01")
    assert re.match(REGEX_DATA, "2005-07-31")
    assert not re.match(REGEX_DATA, "Data")
    assert not re.match(REGEX_DATA, "REGIAO:")


def test_19_colunas():
    assert len(COLUNAS_BDMEP) == 19
