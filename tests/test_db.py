import pytest

from modules.db import DBConfigError, crear_cliente


@pytest.mark.parametrize("secrets", [
    {},
    {"supabase": {"url": "https://x.supabase.co"}},
    {"supabase": {"url": "http://x", "service_role_key": "k"}},
    {"supabase": {"url": "https://x.supabase.co", "service_role_key": "REEMPLAZAR"}},
])
def test_secretos_invalidos(secrets):
    with pytest.raises(DBConfigError):
        crear_cliente(secrets)
