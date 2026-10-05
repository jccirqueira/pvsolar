"""
Unit tests for SMA inverter driver.
"""

import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.config import InverterConfig, ModbusConnection
from drivers.base import InverterData
from drivers.sma.driver import SMADriver


@pytest.fixture
def sma_config():
    return InverterConfig(
        id="sma-001",
        name="SMA Sunny Boy 5.0",
        driver="sma",
        connection=ModbusConnection(
            host="192.168.1.100",
            port=502,
            unit_id=3
        )
    )


class TestSMADriver:
    """Tests for SMADriver class."""

    def test_driver_initialization(self, sma_config):
        driver = SMADriver(sma_config)
        assert driver.config.id == "sma-001"
        assert driver._profile == "sma"
        assert driver._num_phases == 3
        assert driver._connected is False

    def test_decode_uint32(self, sma_config):
        driver = SMADriver(sma_config)

        # Test normal value
        assert driver._decode_uint32([0x0000, 0x1000]) == 4096

        # Test invalid value (0x7FFFFFFF)
        assert driver._decode_uint32([0x7FFF, 0xFFFF]) == 0

        # Test zero
        assert driver._decode_uint32([0x0000, 0x0000]) == 0

    def test_decode_int32(self, sma_config):
        driver = SMADriver(sma_config)

        # Test positive value
        assert driver._decode_int32([0x0000, 0x03E8]) == 1000

        # Test negative value (0xFFFFFFFF = -1)
        assert driver._decode_int32([0xFFFF, 0xFFFF]) == -1

        # Test invalid value (0x7FFFFFFF)
        assert driver._decode_int32([0x7FFF, 0xFFFF]) == 0

    def test_decode_int16(self, sma_config):
        driver = SMADriver(sma_config)

        # Test positive value
        assert driver._decode_int16(100) == 100

        # Test negative value
        assert driver._decode_int16(65436) == -100

    def test_decode_ascii(self, sma_config):
        driver = SMADriver(sma_config)

        # Test "SMA" string
        registers = [0x534D, 0x4100]  # "SM" + "A\0"
        result = driver._decode_ascii(registers)
        assert "SMA" in result

    def test_decode_sma_status(self, sma_config):
        driver = SMADriver(sma_config)

        assert driver._decode_sma_status(0) == "off"
        assert driver._decode_sma_status(100) == "standby"
        assert driver._decode_sma_status(300) == "starting"
        assert driver._decode_sma_status(600) == "running"
        assert driver._decode_sma_status(800) == "fault"
        assert driver._decode_sma_status(1300) == "shutdown"

    def test_inverter_data_structure(self, sma_config):
        driver = SMADriver(sma_config)

        # Verify register addresses are defined
        assert driver.SMA_REG_DC_CURRENT == 30769
        assert driver.SMA_REG_AC_POWER_TOTAL == 30775
        assert driver.SMA_REG_TOTAL_YIELD_WH == 30529
        assert driver.SMA_REG_HEATSINK_TEMP == 34109


# ---------------------------------------------------------------
# Helpers com cliente Modbus falso
# ---------------------------------------------------------------

class FakeResponse:
    """Resposta Modbus falsa (mimetiza a interface do pymodbus)."""

    def __init__(self, registers=None, error=False):
        self.registers = list(registers or [])
        self._error = error

    def isError(self):
        return self._error


class FakeModbusClient:
    """Cliente Modbus TCP falso, usado tambem como factory do driver."""

    def __init__(self, handler=None, connect_result=True):
        self.handler = handler
        self.connect_result = connect_result
        self.closed = False
        self.calls = []

    def __call__(self, host=None, port=None, timeout=None, retries=None, **kwargs):
        # O driver chama AsyncModbusTcpClient(...) como factory
        return self

    async def connect(self):
        return self.connect_result

    def close(self):
        self.closed = True

    async def read_holding_registers(self, address, count=1, slave=1):
        self.calls.append(("rh", address, count, slave))
        return self._dispatch("rh", address)

    async def read_input_registers(self, address, count=1, slave=1):
        self.calls.append(("ri", address, count, slave))
        return self._dispatch("ri", address)

    async def write_register(self, address, value, slave=1):
        self.calls.append(("wr", address, value, slave))
        return self._dispatch("wr", address)

    def _dispatch(self, method, address):
        if self.handler is None:
            return FakeResponse(error=True)
        return self.handler(method, address, 1, 1)


def regs_str(text: str, n_regs: int) -> list[int]:
    """Converte texto em exatamente n_regs registradores ASCII."""
    padded = text.ljust(n_regs * 2, "\x00")
    return [(ord(padded[i]) << 8) | ord(padded[i + 1]) for i in range(0, len(padded), 2)]


def int32_regs(value: int) -> list[int]:
    """Converte um inteiro (com sinal) em 2 registradores big endian."""
    return [(value >> 16) & 0xFFFF, value & 0xFFFF]


def float_to_regs(value: float) -> list[int]:
    """Converte um float32 IEEE 754 em 2 registradores (big endian)."""
    raw = struct.unpack("I", struct.pack("f", value))[0]
    return [raw >> 16, raw & 0xFFFF]


def sma_dc_regs(current=8000, voltage=320000, power=5120) -> list[int]:
    """Payload DC do perfil SMA (6 registradores)."""
    return int32_regs(current) + int32_regs(voltage) + int32_regs(power)


def sma_ac_regs() -> list[int]:
    """Payload AC do perfil SMA (24 registradores)."""
    regs = [0] * 24
    regs[0:2] = int32_regs(5000)        # Pac total = 5000 W
    for i in range(3):
        regs[8 + i * 2:10 + i * 2] = int32_regs(230000)   # Vac -> 230.0 V
        regs[14 + i * 2:16 + i * 2] = int32_regs(7500)    # Iac -> 7.5 A
    regs[20:22] = int32_regs(50000)     # freq -> 50.0 Hz
    return regs


def sma_energy_regs() -> list[int]:
    """Payload de energia do perfil SMA (12 registradores)."""
    regs = [0] * 12
    regs[0:2] = int32_regs(1_000_000)   # total em Wh
    regs[8:10] = int32_regs(25)         # diario em kWh
    return regs


def sma_temp_regs() -> list[int]:
    """Payload de temperatura do perfil SMA (8 registradores)."""
    regs = [0] * 8
    regs[0:2] = int32_regs(455)         # dissipador -> 45.5 C
    regs[4:6] = int32_regs(380)         # interna -> 38.0 C
    return regs


def sma_handler(method, address, count, slave):
    """Responde as leituras do perfil SMA completo."""
    if method == "ri":
        tabela = {
            30057: regs_str("SMA1234", 4),
            30769: sma_dc_regs(),
            30775: sma_ac_regs(),
            30529: sma_energy_regs(),
            34109: sma_temp_regs(),
            30201: int32_regs(600),
        }
        if address in tabela:
            return FakeResponse(tabela[address])
    return FakeResponse(error=True)


def base_config(unit_id=3) -> InverterConfig:
    """Configuracao valida para o driver SMA."""
    return InverterConfig(
        id="sma-001",
        name="SMA Sunny Boy 5.0",
        driver="sma",
        connection=ModbusConnection(host="192.168.1.100", port=502, unit_id=unit_id)
    )


def make_driver(handler=None, unit_id=3, profile="sma") -> SMADriver:
    """Cria o driver ja com cliente falso injetado e unidade definida."""
    driver = SMADriver(base_config(unit_id))
    driver._client = FakeModbusClient(handler)
    driver._unit_id = unit_id
    driver._profile = profile
    return driver


def common_model_regs() -> list[int]:
    """Payload do Common Model SunSpec (72 registradores)."""
    return (
        regs_str("SMA", 16)
        + regs_str("Sunny Tripower", 16)
        + regs_str("OPTION", 16)
        + regs_str("2.1.0", 8)
        + regs_str("SMA12345", 16)
    )


def inverter_int_regs() -> list[int]:
    """Payload do inverter model inteiro (101-103), 50 registradores."""
    regs = [0] * 50
    regs[2] = 4                    # estado: running
    regs[3] = 65535                # sf_power = -1
    regs[4] = 50000                # ac_power = 5000.0 W
    regs[12] = 50000               # frequencia bruta
    regs[14] = 2300                # tensao -> 230.0 V
    regs[15] = 100                 # corrente
    return regs


def inverter_float_regs() -> list[int]:
    """Payload do inverter model float (111-113), 45 registradores."""
    regs = [0] * 45
    regs[3] = 4                                # estado: running
    regs[4], regs[5] = float_to_regs(5000.0)
    regs[12], regs[13] = float_to_regs(50.02)
    regs[14], regs[15] = float_to_regs(230.1)
    regs[16], regs[17] = float_to_regs(7.5)
    return regs


class TestSMAConnect:
    """Tests for SMADriver.connect/disconnect."""

    async def test_connect_sucesso_perfil_sma(self, monkeypatch):
        def handler(method, address, count, slave):
            if method == "rh" and address == 40000:
                return FakeResponse(error=True)
            if method == "ri" and address == 30053:
                return FakeResponse(int32_regs(1000))
            if method == "ri" and 30773 <= address <= 30781:
                return FakeResponse(int32_regs(5000))
            return FakeResponse(error=True)

        fake = FakeModbusClient(handler)
        monkeypatch.setattr("drivers.sma.driver.AsyncModbusTcpClient", fake)

        driver = SMADriver(base_config())
        await driver.connect()

        assert driver._connected is True
        assert driver._profile == "sma"
        assert driver._unit_id == 3
        assert driver._num_phases == 3
        assert driver._num_strings == 4

    async def test_connect_sucesso_perfil_sunspec(self, monkeypatch):
        def handler(method, address, count, slave):
            if method == "rh" and address == 40000:
                # "SunS" = 0x53756E53
                return FakeResponse([0x5375, 0x6E53, 0, 0])
            return FakeResponse(error=True)

        fake = FakeModbusClient(handler)
        monkeypatch.setattr("drivers.sma.driver.AsyncModbusTcpClient", fake)

        driver = SMADriver(base_config())
        await driver.connect()

        assert driver._connected is True
        assert driver._profile == "sunspec"
        assert driver._unit_id == 126

    async def test_connect_falha_levanta_connection_error(self, monkeypatch):
        fake = FakeModbusClient(connect_result=False)
        monkeypatch.setattr("drivers.sma.driver.AsyncModbusTcpClient", fake)

        driver = SMADriver(base_config())
        with pytest.raises(ConnectionError, match="Failed to connect to SMA"):
            await driver.connect()

        assert driver._connected is False
        assert driver._error_count == 1

    async def test_disconnect(self):
        driver = make_driver()
        client = FakeModbusClient()
        driver._client = client
        driver._connected = True

        await driver.disconnect()

        assert client.closed is True
        assert driver._connected is False

    async def test_disconnect_sem_cliente(self):
        driver = SMADriver(base_config())
        # Sem cliente registrado: nada a fechar
        await driver.disconnect()
        assert driver._connected is False


class TestSMADetectProfile:
    """Tests for SMADriver._detect_profile fallbacks."""

    async def test_fallback_unidade_configurada(self):
        # SunSpec e perfil SMA indisponiveis -> usa a unidade do config
        driver = make_driver(
            lambda method, address, count, slave: FakeResponse(error=True),
            unit_id=9,
        )

        await driver._detect_profile()

        assert driver._profile == "sma"
        assert driver._unit_id == 9

    async def test_fallback_excecao(self):
        def handler(method, address, count, slave):
            raise RuntimeError("timeout de rede")

        driver = make_driver(handler, unit_id=7)

        await driver._detect_profile()

        assert driver._profile == "sma"
        assert driver._unit_id == 7


class TestSMACapabilities:
    """Tests for SMADriver._detect_capabilities."""

    async def test_detect_fases_e_strings_reduzidas(self):
        def handler(method, address, count, slave):
            if address == 30053:
                return FakeResponse(int32_regs(1000))
            if address in (30777, 30773):
                return FakeResponse(int32_regs(5000))
            return FakeResponse(error=True)

        driver = make_driver(handler)

        await driver._detect_capabilities()

        # So L1 responde: 30777 atende fases=1 e tambem strings=3
        assert driver._num_phases == 1
        assert driver._num_strings == 3

    async def test_detect_todas_leituras_erro(self):
        driver = make_driver(
            lambda method, address, count, slave: FakeResponse(error=True)
        )

        await driver._detect_capabilities()

        # Sem resposta, os padroes do __init__ permanecem
        assert driver._num_phases == 3
        assert driver._num_strings == 2

    async def test_detect_excecao(self):
        def handler(method, address, count, slave):
            raise RuntimeError("registro invalido")

        driver = make_driver(handler)

        await driver._detect_capabilities()

        assert driver._num_phases == 3
        assert driver._num_strings == 2


class TestSMAReadAll:
    """Tests for SMADriver.read_all in both profiles."""

    async def test_read_all_perfil_sma_completo(self):
        driver = make_driver(sma_handler, unit_id=3)

        data = await driver.read_all()

        assert data is not None
        assert data.manufacturer == "SMA"
        assert data.serial_number == "SMA1234"
        assert data.custom["profile"] == "sma"
        assert data.custom["unit_id"] == 3

        # DC
        assert len(data.dc_inputs) == 1
        assert data.dc_inputs[0]["voltage"] == pytest.approx(320.0)
        assert data.dc_inputs[0]["current"] == pytest.approx(8.0)
        assert data.dc_inputs[0]["power"] == 5120

        # AC
        assert data.ac_power == 5000
        assert data.ac_voltage == pytest.approx([230.0, 230.0, 230.0])
        assert data.ac_current == pytest.approx([7.5, 7.5, 7.5])
        assert data.ac_frequency == pytest.approx(50.0)

        # Energia, temperatura e status
        assert data.total_energy == 1_000_000
        assert data.daily_energy == 25_000
        assert data.temperature == pytest.approx(45.5)
        assert data.custom["internal_temp"] == pytest.approx(38.0)
        assert data.status == "running"
        assert data.operating_state == 600
        assert data.efficiency == pytest.approx(5000 / 5120 * 100)
        assert driver._last_read is not None
        assert driver._consecutive_errors == 0

    async def test_read_all_serial_com_excecao(self):
        def handler(method, address, count, slave):
            if method == "ri" and address == 30057:
                raise RuntimeError("registro bloqueado")
            return sma_handler(method, address, count, slave)

        driver = make_driver(handler, unit_id=3)

        data = await driver.read_all()

        # A falha na leitura da serie e engolida pelo try/except local
        assert data is not None
        assert data.serial_number == ""
        assert data.ac_power == 5000

    async def test_read_all_dc_negativo_zera(self):
        def handler(method, address, count, slave):
            if method == "ri" and address == 30769:
                return FakeResponse(
                    sma_dc_regs(current=-5, voltage=-10, power=-100)
                )
            return sma_handler(method, address, count, slave)

        driver = make_driver(handler, unit_id=3)

        data = await driver.read_all()

        assert data is not None
        # Valores negativos sao clampados para zero
        assert data.dc_inputs[0]["voltage"] == 0
        assert data.dc_inputs[0]["current"] == 0
        assert data.dc_inputs[0]["power"] == 0

    async def test_read_all_falha_de_rede_retorna_none(self):
        def handler(method, address, count, slave):
            if method == "ri" and address == 30769:
                raise RuntimeError("cliente offline")
            if method == "ri" and address == 30057:
                return FakeResponse(regs_str("SMA1234", 4))
            return FakeResponse(error=True)

        driver = make_driver(handler, unit_id=3)

        data = await driver.read_all()

        assert data is None
        assert driver._error_count == 1

    async def test_read_all_perfil_sunspec_inteiro(self):
        def handler(method, address, count, slave):
            if method != "rh":
                return FakeResponse(error=True)
            chain = {40000: [1, 72], 40074: [103, 50], 40126: [0xFFFF, 0]}
            payload = {40002: common_model_regs(), 40076: inverter_int_regs()}
            if address in chain:
                return FakeResponse(chain[address])
            if address in payload:
                return FakeResponse(payload[address])
            return FakeResponse(error=True)

        driver = make_driver(handler, unit_id=126, profile="sunspec")

        data = await driver.read_all()

        assert data is not None
        assert data.manufacturer == "SMA"
        assert data.model == "Sunny Tripower"
        assert data.firmware_version == "2.1.0"
        assert data.serial_number == "SMA12345"
        assert data.ac_power == 5000.0
        assert data.ac_frequency == pytest.approx(50.0)
        assert data.ac_voltage == [230.0]
        assert data.ac_current == [pytest.approx(0.1)]
        assert data.status == "running"
        assert data.operating_state == 4

    async def test_read_all_perfil_sunspec_float(self):
        def handler(method, address, count, slave):
            if method != "rh":
                return FakeResponse(error=True)
            chain = {40000: [1, 72], 40074: [111, 45], 40121: [0xFFFF, 0]}
            payload = {40002: common_model_regs(), 40076: inverter_float_regs()}
            if address in chain:
                return FakeResponse(chain[address])
            if address in payload:
                return FakeResponse(payload[address])
            return FakeResponse(error=True)

        driver = make_driver(handler, unit_id=126, profile="sunspec")

        data = await driver.read_all()

        assert data is not None
        assert data.ac_power == pytest.approx(5000.0)
        assert data.ac_frequency == pytest.approx(50.02, rel=1e-5)
        assert data.ac_voltage == [pytest.approx(230.1, rel=1e-5)]
        assert data.ac_current == [pytest.approx(7.5)]
        assert data.status == "running"

    async def test_read_all_perfil_sunspec_sem_modelos(self):
        driver = make_driver(
            lambda method, address, count, slave: FakeResponse(error=True),
            unit_id=126,
            profile="sunspec",
        )

        data = await driver.read_all()

        # Cadeia vazia: comum e inversor nao sao lidos
        assert data is not None
        assert data.manufacturer == "SMA"
        assert data.ac_power == 0.0
        assert data.status == "unknown"


class TestSMAGetStatus:
    """Tests for SMADriver.get_status."""

    @pytest.mark.parametrize("code,esperado", [
        (0, "off"),
        (100, "standby"),
        (400, "starting"),
        (600, "running"),
        (900, "fault"),
        (1300, "shutdown"),
        (2048, "unknown"),
    ])
    async def test_get_status_perfil_sma(self, code, esperado):
        driver = make_driver(
            lambda method, address, count, slave: FakeResponse(int32_regs(code)),
            unit_id=3,
        )

        assert await driver.get_status() == esperado

    async def test_get_status_perfil_sma_resposta_erro(self):
        driver = make_driver(
            lambda method, address, count, slave: FakeResponse(error=True),
            unit_id=3,
        )

        # Sem status legivel o metodo cai no fim do try e retorna None
        assert await driver.get_status() is None

    async def test_get_status_excecao(self):
        def handler(method, address, count, slave):
            raise RuntimeError("cliente offline")

        driver = make_driver(handler, unit_id=3)

        assert await driver.get_status() == "error"

    async def test_get_status_perfil_sunspec(self):
        driver = make_driver(profile="sunspec", unit_id=126)

        async def com_dados():
            return InverterData()

        async def sem_dados():
            return None

        driver.read_all = com_dados
        assert await driver.get_status() == "unknown"

        # Dados reais devolvem o status decodificado
        dados = InverterData()
        dados.status = "running"

        async def dados_corridos():
            return dados

        driver.read_all = dados_corridos
        assert await driver.get_status() == "running"

        driver.read_all = sem_dados
        assert await driver.get_status() == "unknown"


class TestSMARegOperations:
    """Tests for SMADriver register read/write helpers."""

    async def test_read_register_sucesso(self):
        driver = make_driver(
            lambda method, address, count, slave: FakeResponse([21, 22]),
            unit_id=3,
        )

        values = await driver.read_register(30000, count=2)

        assert values == [21, 22]
        assert driver._client.calls[-1] == ("ri", 30000, 2, 3)

    async def test_read_register_erro(self):
        driver = make_driver(
            lambda method, address, count, slave: FakeResponse(error=True),
            unit_id=3,
        )

        erro = None
        try:
            await driver.read_register(30000)
        except Exception as exc:
            erro = exc

        assert erro is not None
        assert "Read error" in str(erro)

    async def test_write_register_sucesso(self):
        driver = make_driver(
            lambda method, address, count, slave: FakeResponse(), unit_id=3
        )

        assert await driver.write_register(40151, 5000) is True
        assert driver._client.calls[-1] == ("wr", 40151, 5000, 3)

    async def test_write_register_erro(self):
        driver = make_driver(
            lambda method, address, count, slave: FakeResponse(error=True),
            unit_id=3,
        )

        assert await driver.write_register(40151, 5000) is False

    async def test_set_active_power_limit_sma(self):
        driver = make_driver(
            lambda method, address, count, slave: FakeResponse(), unit_id=3
        )

        assert await driver.set_active_power_limit(75.5) is True
        # 75.5% com resolucao de 0.01% -> 7550 no registrador 40151
        assert driver._client.calls[-1] == ("wr", 40151, 7550, 3)

    async def test_set_active_power_limit_sunspec_negado(self):
        driver = make_driver(
            lambda method, address, count, slave: FakeResponse(),
            unit_id=126,
            profile="sunspec",
        )

        # Limite de potencia so existe no perfil SMA
        assert await driver.set_active_power_limit(75.5) is False
        assert driver._client.calls == []


class TestSMADecoders:
    """Tests for SMA low-level decoders."""

    def test_decode_uint32_curto(self, sma_config):
        driver = SMADriver(sma_config)
        # Menos de 2 registradores retorna 0
        assert driver._decode_uint32([1]) == 0

    def test_decode_int32_curto(self, sma_config):
        driver = SMADriver(sma_config)
        # Menos de 2 registradores retorna 0
        assert driver._decode_int32([1]) == 0

    def test_decode_float32(self, sma_config):
        driver = SMADriver(sma_config)
        # Entrada curta retorna 0.0
        assert driver._decode_float32([1]) == 0.0
        assert driver._decode_float32(float_to_regs(-2.5)) == -2.5

    def test_decode_ascii_ignora_nao_imprimivel(self, sma_config):
        driver = SMADriver(sma_config)
        # 0x0001 esta fora da faixa 32..126 e e descartado
        assert driver._decode_ascii([0x534D, 0x0001, 0x4100]) == "SMA"

    def test_decode_sma_status_desconhecido(self, sma_config):
        driver = SMADriver(sma_config)
        assert driver._decode_sma_status(2048) == "unknown"
        assert driver._decode_sma_status(9999) == "unknown"
