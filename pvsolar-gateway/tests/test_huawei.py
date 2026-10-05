"""
Unit tests for Huawei inverter driver.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.config import InverterConfig, ModbusConnection
from drivers.base import InverterData
from drivers.huawei.driver import HuaweiDriver


@pytest.fixture
def huawei_config():
    return InverterConfig(
        id="huawei-001",
        name="Huawei SUN2000-5KTL",
        driver="huawei",
        connection=ModbusConnection(
            host="192.168.1.101",
            port=502,
            unit_id=1
        )
    )


class TestHuaweiDriver:
    """Tests for HuaweiDriver class."""

    def test_driver_initialization(self, huawei_config):
        driver = HuaweiDriver(huawei_config)
        assert driver.config.id == "huawei-001"
        assert driver._series == "unknown"
        assert driver._num_mppt == 2
        assert driver._has_battery is False
        assert driver._connected is False

    def test_decode_uint32(self, huawei_config):
        driver = HuaweiDriver(huawei_config)

        # Test normal value
        assert driver._decode_uint32([0x0000, 0x1000]) == 4096

        # Test zero
        assert driver._decode_uint32([0x0000, 0x0000]) == 0

    def test_decode_int32(self, huawei_config):
        driver = HuaweiDriver(huawei_config)

        # Test positive value
        assert driver._decode_int32([0x0000, 0x03E8]) == 1000

        # Test negative value (0xFFFFFFFF = -1)
        assert driver._decode_int32([0xFFFF, 0xFFFF]) == -1

    def test_decode_int16(self, huawei_config):
        driver = HuaweiDriver(huawei_config)

        # Test positive value
        assert driver._decode_int16(100) == 100

        # Test negative value
        assert driver._decode_int16(65436) == -100

    def test_decode_string(self, huawei_config):
        driver = HuaweiDriver(huawei_config)

        # Test "Huawei" string
        registers = [0x4875, 0x6177, 0x6569]  # "Hu", "aw", "ei"
        result = driver._decode_string(registers)
        assert "Huawei" in result

    def test_decode_huawei_state(self, huawei_config):
        driver = HuaweiDriver(huawei_config)

        assert driver._decode_huawei_state(0) == "standby"
        assert driver._decode_huawei_state(256) == "starting"
        assert driver._decode_huawei_state(512) == "running"
        assert driver._decode_huawei_state(513) == "running"
        assert driver._decode_huawei_state(768) == "fault"
        assert driver._decode_huawei_state(769) == "shutdown"
        assert driver._decode_huawei_state(40960) == "standby"

    def test_register_addresses(self, huawei_config):
        driver = HuaweiDriver(huawei_config)

        # DC side registers
        assert driver.REG_PV1_VOLTAGE == 32016
        assert driver.REG_PV1_CURRENT == 32017
        assert driver.REG_DC_POWER == 32064

        # AC side registers
        assert driver.REG_GRID_VOLTAGE_L1 == 32069
        assert driver.REG_ACTIVE_POWER == 32080
        assert driver.REG_GRID_FREQUENCY == 32085

        # Energy registers
        assert driver.REG_DAILY_YIELD == 32106
        assert driver.REG_TOTAL_YIELD == 32109

        # Battery registers
        assert driver.REG_BATTERY_SOC == 37000
        assert driver.REG_BATTERY_POWER == 37003

    def test_model_detection_series(self, huawei_config):
        driver = HuaweiDriver(huawei_config)

        # Test series classification
        assert driver._decode_huawei_state(512) == "running"
        assert driver._decode_huawei_state(768) == "fault"

    def test_inverter_data_structure(self, huawei_config):
        driver = HuaweiDriver(huawei_config)

        # Verify driver has all required methods
        assert hasattr(driver, 'connect')
        assert hasattr(driver, 'disconnect')
        assert hasattr(driver, 'read_all')
        assert hasattr(driver, 'get_status')
        assert hasattr(driver, 'read_register')
        assert hasattr(driver, 'write_register')
        assert hasattr(driver, 'set_active_power_limit')


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
        return self._dispatch(address)

    async def write_register(self, address, value, slave=1):
        self.calls.append(("wr", address, value, slave))
        return self._dispatch(address)

    def _dispatch(self, address):
        if self.handler is None:
            return FakeResponse(error=True)
        return self.handler("rh", address, 1, 1)


def regs_str(text: str, n_regs: int) -> list[int]:
    """Converte texto em exatamente n_regs registradores ASCII."""
    padded = text.ljust(n_regs * 2, "\x00")
    return [(ord(padded[i]) << 8) | ord(padded[i + 1]) for i in range(0, len(padded), 2)]


def base_config() -> InverterConfig:
    """Configuracao valida para o driver Huawei."""
    return InverterConfig(
        id="huawei-001",
        name="Huawei SUN2000-5KTL",
        driver="huawei",
        connection=ModbusConnection(host="192.168.1.101", port=502, unit_id=1)
    )


def make_driver(handler=None) -> HuaweiDriver:
    """Cria o driver ja com cliente falso injetado."""
    driver = HuaweiDriver(base_config())
    driver._client = FakeModbusClient(handler)
    return driver


def telemetry_table() -> dict:
    """Registradores de telemetria do SUN2000 usados nos testes."""
    return {
        30000: regs_str("SUN2000-5KTL-M1", 15),
        30015: regs_str("HR12345678", 10),
        30025: regs_str("V100R001C00", 15),
        30040: regs_str("V100R001C20", 15),
        32016: [3200],                 # PV1 tensao -> 320.0 V
        32017: [800],                  # PV1 corrente -> 8.0 A
        32018: [3180],                 # PV2 tensao -> 318.0 V
        32019: [810],                  # PV2 corrente -> 8.1 A
        32064: [0, 5120],              # DC power total
        32069: [2300],                 # Vac L1 -> 230.0 V
        32070: [2310],
        32071: [2290],
        32072: [750],                  # Iac L1 -> 7.5 A
        32074: [760],
        32076: [740],
        32078: [0xFFFF, 0xFC18],       # reativa -> -1000 var
        32080: [0, 5000],              # potencia ativa -> 5000 W
        32082: [980],                  # fator de potencia -> 0.98
        32085: [5000],                 # frequencia -> 50.0 Hz
        32087: [425],                  # temperatura -> 42.5 C
        32089: [512],                  # run state: on-grid
        32090: [0],                    # fault code
        32106: [0, 25000],             # rendimento diario -> 250.000.000 Wh
        32109: [1, 0],                 # rendimento total -> 655.360.000 Wh
        37000: [850],                  # SOC -> 85.0 %
        37001: [530],                  # tensao bateria -> 53.0 V
        37002: [65500],                # corrente bateria -> -3.6 A
        37003: [0, 2500],              # potencia bateria -> 2500 W
        37049: [4],                    # otimizadores
    }


def telemetry_handler(method, address, count, slave):
    """Responde a tabela de telemetria; desconhecidos retornam zerados."""
    tabela = telemetry_table()
    if address in tabela:
        return FakeResponse(tabela[address])
    return FakeResponse([0])


class TestHuaweiDetectModel:
    """Tests for HuaweiDriver._detect_model."""

    @pytest.mark.parametrize("model_id,serie", [
        (0, "L0"),
        (99, "L0"),
        (100, "L1"),
        (200, "L2"),
        (300, "L3"),
        (400, "M0"),
        (500, "M1"),
        (600, "M2"),
        (700, "M3"),
        (800, "MA"),
        (900, "MB0"),
        (1000, "unknown"),
    ])
    async def test_detect_model_series(self, model_id, serie):
        def handler(method, address, count, slave):
            if address == 30079:
                return FakeResponse([model_id])
            if address == 30015:
                return FakeResponse(regs_str("HR12345678", 10))
            return FakeResponse(error=True)

        driver = make_driver(handler)

        await driver._detect_model()

        assert driver._series == serie
        assert driver._serial_raw == regs_str("HR12345678", 10)

    async def test_detect_model_resposta_erro(self):
        driver = make_driver(lambda method, address, count, slave: FakeResponse(error=True))

        await driver._detect_model()

        # Sem leitura valida a serie permanece no padrao
        assert driver._series == "unknown"

    async def test_detect_model_excecao(self):
        def handler(method, address, count, slave):
            raise RuntimeError("registro invalido")

        driver = make_driver(handler)

        await driver._detect_model()

        assert driver._series == "unknown"


class TestHuaweiCapabilities:
    """Tests for HuaweiDriver._detect_capabilities."""

    async def test_detect_capabilities_completo(self):
        def handler(method, address, count, slave):
            # Tensao dos 2 primeiros MPPTs; erro no 3o encerra o loop
            if address in (32016, 32018):
                return FakeResponse([3200])
            if address == 37000:
                return FakeResponse([850])
            if address == 37049:
                return FakeResponse([4])
            return FakeResponse(error=True)

        driver = make_driver(handler)

        await driver._detect_capabilities()

        assert driver._num_mppt == 2
        assert driver._has_battery is True
        assert driver._has_optimizers is True
        assert driver._optimizer_count == 4

    async def test_detect_capabilities_10_mppts_sem_recursos(self):
        def handler(method, address, count, slave):
            if 32016 <= address <= 32034 and address % 2 == 0:
                return FakeResponse([3200])
            if address == 37049:
                return FakeResponse([0])
            return FakeResponse(error=True)

        driver = make_driver(handler)

        await driver._detect_capabilities()

        # Loop completo de 10 MPPTs (nenhuma leitura falhou)
        assert driver._num_mppt == 10
        assert driver._has_battery is False
        assert driver._has_optimizers is False

    async def test_detect_capabilities_excecao(self):
        def handler(method, address, count, slave):
            raise RuntimeError("timeout")

        driver = make_driver(handler)

        await driver._detect_capabilities()

        # A falha zera a contagem e nao marca recursos
        assert driver._num_mppt == 0
        assert driver._has_battery is False
        assert driver._has_optimizers is False


class TestHuaweiReadAll:
    """Tests for HuaweiDriver.read_all and its helpers."""

    def _make_full_driver(self) -> HuaweiDriver:
        driver = make_driver(telemetry_handler)
        driver._series = "M1"
        driver._num_mppt = 2
        driver._has_battery = True
        driver._has_optimizers = True
        return driver

    async def test_read_all_completo(self):
        driver = self._make_full_driver()

        data = await driver.read_all()

        assert data is not None
        assert data.manufacturer == "Huawei"
        assert data.model == "SUN2000-5KTL-M1"
        assert data.serial_number == "HR12345678"
        assert data.firmware_version == "V100R001C20"
        assert data.custom["firmware_sd"] == "V100R001C00"
        assert data.custom["series"] == "M1"
        assert data.custom["num_mppt"] == 2

        # Lado DC
        assert len(data.dc_inputs) == 2
        assert data.dc_inputs[0]["voltage"] == pytest.approx(320.0)
        assert data.dc_inputs[0]["current"] == pytest.approx(8.0)
        assert data.dc_inputs[0]["power"] == pytest.approx(2560.0)
        assert data.dc_inputs[1]["voltage"] == pytest.approx(318.0)
        assert data.dc_inputs[1]["current"] == pytest.approx(8.1)
        assert data.custom["dc_power_total"] == 5120

        # Lado AC
        assert data.ac_voltage == pytest.approx([230.0, 231.0, 229.0])
        assert data.ac_current == pytest.approx([7.5, 7.6, 7.4])
        assert data.ac_power == 5000
        assert data.ac_reactive_power == -1000
        assert data.ac_power_factor == pytest.approx(0.98)
        assert data.ac_frequency == pytest.approx(50.0)

        # Energia, temperatura e status
        assert data.daily_energy == 250_000_000
        assert data.total_energy == 655_360_000
        assert data.temperature == pytest.approx(42.5)
        assert data.status == "running"
        assert data.operating_state == 512
        assert data.fault_code == 0

        # Bateria e otimizadores
        storage = data.custom["storage"]
        assert storage["state_of_charge"] == pytest.approx(85.0)
        assert storage["voltage"] == pytest.approx(53.0)
        assert storage["current"] == pytest.approx(-3.6)
        assert storage["power"] == 2500
        assert storage["mode"] == "charging"
        assert data.custom["optimizer_count"] == 4

        # Eficiencia = ac_power / soma(dc_power) * 100
        assert data.efficiency == pytest.approx(5000 / (2560 + 2575.8) * 100)
        assert driver._last_read is not None
        assert driver._consecutive_errors == 0

    async def test_read_all_todas_leituras_erro(self):
        driver = make_driver(lambda method, address, count, slave: FakeResponse(error=True))
        driver._num_mppt = 2

        data = await driver.read_all()

        # Cada leitura com erro preserva o default do InverterData
        assert data is not None
        assert data.manufacturer == "Huawei"
        assert data.model == ""
        assert data.serial_number == ""
        assert data.dc_inputs == []
        assert "dc_power_total" not in data.custom
        assert data.ac_voltage == []
        assert data.ac_current == []
        assert data.ac_power == 0.0
        assert data.ac_reactive_power == 0.0
        assert data.ac_power_factor == 0.0
        assert data.ac_frequency == 0.0
        assert data.daily_energy == 0.0
        assert data.total_energy == 0.0
        assert data.temperature == 0.0
        assert data.status == "unknown"
        assert data.fault_code == 0
        assert "storage" not in data.custom
        assert "optimizer_count" not in data.custom

    async def test_read_all_falha_de_rede_retorna_none(self):
        def handler(method, address, count, slave):
            raise RuntimeError("cliente offline")

        driver = make_driver(handler)

        data = await driver.read_all()

        assert data is None
        assert driver._error_count == 1

    async def test_read_all_sem_bateria_e_otimizadores(self):
        driver = make_driver(telemetry_handler)
        driver._num_mppt = 2

        data = await driver.read_all()

        assert data is not None
        # Ramos de bateria/otimizador nao executam sem os flags
        assert "storage" not in data.custom
        assert "optimizer_count" not in data.custom

    async def test_read_all_eficiencia_sem_potencia_dc(self):
        def handler(method, address, count, slave):
            if address in (32016, 32018, 32017, 32019):
                return FakeResponse([0])
            return telemetry_handler(method, address, count, slave)

        driver = make_driver(handler)
        driver._num_mppt = 2

        data = await driver.read_all()

        assert data is not None
        # Sem potencia DC a eficiencia fica em zero
        assert data.efficiency == 0.0


class TestHuaweiBattery:
    """Tests for HuaweiDriver._read_battery."""

    @pytest.mark.parametrize("power_regs,modo", [
        ([0, 2500], "charging"),
        ([0xFFFF, 0xFFFF], "discharging"),
        ([0, 0], "idle"),
    ])
    async def test_read_battery_modos(self, power_regs, modo):
        def handler(method, address, count, slave):
            tabela = {
                37000: [850],
                37001: [530],
                37002: [65500],
                37003: power_regs,
            }
            if address in tabela:
                return FakeResponse(tabela[address])
            return FakeResponse(error=True)

        driver = make_driver(handler)
        data = InverterData()

        await driver._read_battery(data)

        storage = data.custom["storage"]
        assert storage["state_of_charge"] == pytest.approx(85.0)
        assert storage["power"] == (-1 if power_regs == [0xFFFF, 0xFFFF] else power_regs[1])
        assert storage["mode"] == modo

    async def test_read_battery_leitura_erro(self):
        def handler(method, address, count, slave):
            if address in (37000, 37001, 37002):
                return FakeResponse([1])
            return FakeResponse(error=True)

        driver = make_driver(handler)
        data = InverterData()

        await driver._read_battery(data)

        # Falha na leitura de potencia descarta o dict inteiro
        assert "storage" not in data.custom


class TestHuaweiOptimizers:
    """Tests for HuaweiDriver._read_optimizers."""

    async def test_read_optimizers(self):
        driver = make_driver(
            lambda method, address, count, slave: FakeResponse([7])
        )
        data = InverterData()

        await driver._read_optimizers(data)

        assert data.custom["optimizer_count"] == 7

    async def test_read_optimizers_erro(self):
        driver = make_driver(
            lambda method, address, count, slave: FakeResponse(error=True)
        )
        data = InverterData()

        await driver._read_optimizers(data)

        assert "optimizer_count" not in data.custom


class TestHuaweiConnection:
    """Tests for HuaweiDriver connection and Modbus operations."""

    async def test_connect_sucesso(self, monkeypatch):
        def handler(method, address, count, slave):
            tabela = {
                30079: [550],
                30015: regs_str("HR12345678", 10),
                32016: [3200],
                32018: [3180],
                37000: [850],
                37049: [0],
            }
            if address in tabela:
                return FakeResponse(tabela[address])
            return FakeResponse(error=True)

        fake = FakeModbusClient(handler)
        monkeypatch.setattr("drivers.huawei.driver.AsyncModbusTcpClient", fake)

        driver = HuaweiDriver(base_config())
        await driver.connect()

        assert driver._connected is True
        assert driver._series == "M1"
        assert driver._num_mppt == 2
        assert driver._has_battery is True
        assert driver._has_optimizers is False

    async def test_connect_falha_levanta_connection_error(self, monkeypatch):
        fake = FakeModbusClient(connect_result=False)
        monkeypatch.setattr("drivers.huawei.driver.AsyncModbusTcpClient", fake)

        driver = HuaweiDriver(base_config())
        with pytest.raises(ConnectionError, match="Failed to connect to Huawei"):
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
        driver = HuaweiDriver(base_config())
        # Sem cliente registrado: nada a fechar
        await driver.disconnect()
        assert driver._connected is False

    @pytest.mark.parametrize("codigo,esperado", [
        (512, "running"),
        (0, "standby"),
        (256, "starting"),
        (768, "fault"),
        (769, "shutdown"),
    ])
    async def test_get_status(self, codigo, esperado):
        driver = make_driver(
            lambda method, address, count, slave: FakeResponse([codigo])
        )

        assert await driver.get_status() == esperado

    async def test_get_status_resposta_erro(self):
        driver = make_driver(
            lambda method, address, count, slave: FakeResponse(error=True)
        )

        assert await driver.get_status() == "unknown"

    async def test_get_status_excecao(self):
        def handler(method, address, count, slave):
            raise RuntimeError("cliente offline")

        driver = make_driver(handler)

        assert await driver.get_status() == "error"

    async def test_read_register_sucesso(self):
        driver = make_driver(
            lambda method, address, count, slave: FakeResponse([11, 12])
        )

        values = await driver.read_register(30000, count=2)

        assert values == [11, 12]
        assert driver._client.calls[-1] == ("rh", 30000, 2, 1)

    async def test_read_register_erro(self):
        driver = make_driver(
            lambda method, address, count, slave: FakeResponse(error=True)
        )

        erro = None
        try:
            await driver.read_register(30000)
        except Exception as exc:
            erro = exc

        assert erro is not None
        assert "Read error" in str(erro)

    async def test_write_register_sucesso(self):
        driver = make_driver(lambda method, address, count, slave: FakeResponse())

        assert await driver.write_register(32086, 5000) is True
        assert driver._client.calls[-1] == ("wr", 32086, 5000, 1)

    async def test_write_register_erro(self):
        driver = make_driver(
            lambda method, address, count, slave: FakeResponse(error=True)
        )

        assert await driver.write_register(32086, 5000) is False

    async def test_set_active_power_limit(self):
        driver = make_driver(lambda method, address, count, slave: FakeResponse())

        assert await driver.set_active_power_limit(50.0) is True
        # 50% com resolucao de 0.01% -> 5000 no registrador 32086
        assert driver._client.calls[-1] == ("wr", 32086, 5000, 1)

    @pytest.mark.parametrize("mode,valor", [
        ("fixed_pf", 0),
        ("cosphi_p", 1),
        ("q_u", 2),
        ("pf_u", 3),
        ("q_p", 4),
        ("desconhecido", 0),
    ])
    async def test_set_reactive_power_control(self, mode, valor):
        driver = make_driver(lambda method, address, count, slave: FakeResponse())

        assert await driver.set_reactive_power_control(mode) is True
        assert driver._client.calls[-1] == ("wr", 32083, valor, 1)


class TestHuaweiDecoders:
    """Tests for HuaweiDriver low-level decoders with short inputs."""

    def test_decode_uint32_curto(self, huawei_config):
        driver = HuaweiDriver(huawei_config)
        # Menos de 2 registradores retorna 0
        assert driver._decode_uint32([1]) == 0

    def test_decode_int32_curto(self, huawei_config):
        driver = HuaweiDriver(huawei_config)
        # Menos de 2 registradores retorna 0
        assert driver._decode_int32([1]) == 0
