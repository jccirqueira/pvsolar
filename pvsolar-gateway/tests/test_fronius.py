"""
Unit tests for Fronius inverter driver.
"""

import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.config import InverterConfig, ModbusConnection
from drivers.base import InverterData
from drivers.fronius.driver import FroniusDriver


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
        return self._dispatch("rh", address, count, slave)

    async def read_input_registers(self, address, count=1, slave=1):
        self.calls.append(("ri", address, count, slave))
        return self._dispatch("ri", address, count, slave)

    async def write_register(self, address, value, slave=1):
        self.calls.append(("wr", address, value, slave))
        return self._dispatch("wr", address, value, slave)

    def _dispatch(self, method, address, count, slave):
        if self.handler is None:
            return FakeResponse(error=True)
        return self.handler(method, address, count, slave)


# ---------------------------------------------------------------
# Helpers de montagem de payloads
# ---------------------------------------------------------------

def str_to_regs(text: str) -> list[int]:
    """Converte texto em registradores SunSpec (2 caracteres por registrador)."""
    if len(text) % 2:
        text += "\x00"
    return [(ord(text[i]) << 8) | ord(text[i + 1]) for i in range(0, len(text), 2)]


def regs_str(text: str, n_regs: int) -> list[int]:
    """Preenche o texto com NUL ate ter exatamente n_regs registradores."""
    return str_to_regs(text.ljust(n_regs * 2, "\x00"))


def float_to_regs(value: float) -> list[int]:
    """Converte um float32 IEEE 754 em 2 registradores (big endian)."""
    raw = struct.unpack("I", struct.pack("f", value))[0]
    return [raw >> 16, raw & 0xFFFF]


def common_model_regs() -> list[int]:
    """Payload do Common Model SunSpec (72 registradores)."""
    return (
        regs_str("Fronius", 16)
        + regs_str("SYMO CORE 4.0", 16)
        + regs_str("OPTION", 16)
        + regs_str("1.2.3", 8)
        + regs_str("SN12345", 16)
    )


def inverter_int_regs() -> list[int]:
    """Payload do inverter model inteiro (103/102/101), 50 registradores."""
    regs = [0] * 50
    regs[2] = 4                    # estado (modo inteiro): running
    regs[3] = 65535                # sf_power = -1
    regs[4] = 50000                # ac_power = 5000.0 W
    regs[6] = 50000                # aparente = 5000.0 VA
    regs[8] = 10000                # reativa = 1000.0 VAR
    regs[9] = 65535                # sf_voltage = -1
    regs[10] = 1000                # fator de potencia = 1.0
    regs[11] = 65535               # sf_current = -1
    regs[12] = 50000               # frequencia bruta
    regs[13] = 65533               # sf_frequency = -3 -> 50.0 Hz
    regs[14] = regs[15] = regs[16] = 2300   # tensoes -> 230.0 V
    regs[17] = regs[18] = regs[19] = 100    # correntes -> 10.0 A
    regs[20] = 3200                # DC1 tensao -> 320.0 V
    regs[21] = 80                  # DC1 corrente -> 8.0 A
    regs[27] = 100                 # energia total (uint64 em [24:28])
    regs[28] = 5000                # energia diaria
    regs[31] = 65535               # sf_energy = -1
    regs[37] = 300                 # temperatura -> 30.0 C
    return regs


def inverter_float_regs() -> list[int]:
    """Payload do float model (113/112/111), 45 registradores."""
    regs = [0] * 45
    regs[3] = 4                                # estado (modo float): running
    regs[4], regs[5] = float_to_regs(5000.0)
    regs[6], regs[7] = float_to_regs(5200.0)
    regs[8], regs[9] = float_to_regs(-300.0)
    regs[10], regs[11] = float_to_regs(0.98)
    regs[12], regs[13] = float_to_regs(50.02)
    regs[14], regs[15] = float_to_regs(230.1)
    regs[16], regs[17] = float_to_regs(229.9)
    regs[18], regs[19] = float_to_regs(231.2)
    regs[20], regs[21] = float_to_regs(7.5)
    regs[22], regs[23] = float_to_regs(7.4)
    regs[24], regs[25] = float_to_regs(7.6)
    regs[26], regs[27] = float_to_regs(380.0)
    regs[28], regs[29] = float_to_regs(7.5)
    regs[30], regs[31] = float_to_regs(382.0)
    regs[32], regs[33] = float_to_regs(7.3)
    # Em modo float o registrador 37 pertence ao uint64 de energia total
    # ([34:38]), mas tambem e lido como temperatura pelo codigo.
    regs[37] = 15000                          # energia total = 15000 kWh
    regs[38], regs[39] = 0, 25                # energia diaria (uint32)
    return regs


def make_config(unit_id=1) -> InverterConfig:
    """Configuracao valida para o driver Fronius."""
    return InverterConfig(
        id="fronius-001",
        name="Fronius SYMO 4.0",
        driver="fronius",
        connection=ModbusConnection(
            host="192.168.1.102",
            port=502,
            unit_id=unit_id
        )
    )


def make_driver(models=None, handler=None, unit_id=1) -> FroniusDriver:
    """Cria o driver ja com cliente falso injetado."""
    driver = FroniusDriver(make_config(unit_id))
    driver._client = FakeModbusClient(handler)
    if models is not None:
        driver._models = models
    return driver


def chain_handler(unit_regs, error_after=False):
    """Handler com a cadeia de modelos SunSpec 1 -> 103 -> fim."""

    def handler(method, address, count, slave):
        if address == 42109:
            return FakeResponse(unit_regs)
        if address == 40000:
            return FakeResponse([1, 72])
        if address == 40074:
            if error_after:
                return FakeResponse(error=True)
            return FakeResponse([103, 50])
        if address == 40126:
            return FakeResponse([0xFFFF, 0])
        return FakeResponse(error=True)

    return handler


@pytest.fixture
def fronius_config():
    return make_config()


class TestFroniusDriver:
    """Tests for FroniusDriver class."""

    def test_driver_initialization(self, fronius_config):
        driver = FroniusDriver(fronius_config)
        assert driver.config.id == "fronius-001"
        assert driver._device_generation == "unknown"
        assert driver._unit_id == 1
        assert driver._float_mode is False
        assert driver._has_storage is False
        assert driver._connected is False

    async def test_connect_sucesso_detecta_gen24(self, monkeypatch):
        fake = FakeModbusClient(chain_handler([0, 0, 0, 50]))
        monkeypatch.setattr("drivers.fronius.driver.AsyncModbusTcpClient", fake)

        driver = FroniusDriver(make_config())
        await driver.connect()

        assert driver._connected is True
        assert driver._device_generation == "gen24"
        assert driver._unit_id == 1
        assert set(driver._models) == {1, 103}
        assert driver._models[1] == {"address": 40000, "length": 72}
        assert driver._float_mode is False
        assert driver._has_storage is False

    async def test_connect_sucesso_float_e_storage(self, monkeypatch):
        # Cadeia com modelos 113 (float) e 124 (storage)

        def handler(method, address, count, slave):
            chain = {
                42109: [0, 0, 0, 50],
                40000: [1, 72],
                40074: [113, 50],
                40126: [160, 13],
                40141: [124, 8],
                40151: [0xFFFF, 0],
            }
            if address in chain:
                return FakeResponse(chain[address])
            return FakeResponse(error=True)

        fake = FakeModbusClient(handler)
        monkeypatch.setattr("drivers.fronius.driver.AsyncModbusTcpClient", fake)

        driver = FroniusDriver(make_config())
        await driver.connect()

        assert driver._connected is True
        assert set(driver._models) == {1, 113, 160, 124}
        assert driver._float_mode is True
        assert driver._has_storage is True

    async def test_connect_snapinverter_mantem_unit_id(self, monkeypatch):
        fake = FakeModbusClient(chain_handler([0, 0, 0, 200], error_after=True))
        monkeypatch.setattr("drivers.fronius.driver.AsyncModbusTcpClient", fake)

        driver = FroniusDriver(make_config(unit_id=5))
        await driver.connect()

        assert driver._device_generation == "snapinverter"
        # Unidade configurada e mantida no modo SnapINverter
        assert driver._unit_id == 5
        assert set(driver._models) == {1}

    async def test_detect_generation_excecao_fallback_gen24(self, monkeypatch):
        def handler(method, address, count, slave):
            if address == 42109:
                raise RuntimeError("registro indisponivel")
            if address == 40000:
                return FakeResponse([1, 72])
            return FakeResponse(error=True)

        fake = FakeModbusClient(handler)
        monkeypatch.setattr("drivers.fronius.driver.AsyncModbusTcpClient", fake)

        driver = FroniusDriver(make_config())
        await driver.connect()

        assert driver._device_generation == "gen24"
        assert driver._connected is True

    async def test_connect_falha_levanta_connection_error(self, monkeypatch):
        fake = FakeModbusClient(chain_handler([0, 0, 0, 50]), connect_result=False)
        monkeypatch.setattr("drivers.fronius.driver.AsyncModbusTcpClient", fake)

        driver = FroniusDriver(make_config())
        with pytest.raises(ConnectionError, match="Failed to connect to Fronius"):
            await driver.connect()

        assert driver._connected is False
        assert driver._error_count == 1

    async def test_connect_sem_model_chain_conecta_com_modelos_vazios(self, monkeypatch):
        # Primeira leitura da cadeia falha (isError): o __init__
        # inicializa _models = {}, entao o connect NAO levanta
        # AttributeError - entra em degraded mode com a cadeia vazia.

        def handler(method, address, count, slave):
            if address == 42109:
                return FakeResponse([0, 0, 0, 50])
            return FakeResponse(error=True)

        fake = FakeModbusClient(handler)
        monkeypatch.setattr("drivers.fronius.driver.AsyncModbusTcpClient", fake)

        driver = FroniusDriver(make_config())
        await driver.connect()

        assert driver._models == {}
        assert driver._connected is True
        assert driver._error_count == 0

    async def test_disconnect(self, fronius_config):
        driver = FroniusDriver(fronius_config)
        client = FakeModbusClient()
        driver._client = client
        driver._connected = True

        await driver.disconnect()

        assert client.closed is True
        assert driver._connected is False

    async def test_disconnect_sem_cliente(self, fronius_config):
        driver = FroniusDriver(fronius_config)
        # Sem cliente registrado: nada a fechar (nao levanta erro)
        await driver.disconnect()
        assert driver._connected is False

    async def test_detect_generation_resposta_erro(self, monkeypatch):
        # Resposta isError no registro 42109: cai no ramo "gen24" do else

        def handler(method, address, count, slave):
            if address == 42109:
                return FakeResponse(error=True)
            if address == 40000:
                return FakeResponse([1, 72])
            if address == 40074:
                return FakeResponse(error=True)
            return FakeResponse(error=True)

        fake = FakeModbusClient(handler)
        monkeypatch.setattr("drivers.fronius.driver.AsyncModbusTcpClient", fake)

        driver = FroniusDriver(make_config())
        await driver.connect()

        assert driver._device_generation == "gen24"
        assert driver._connected is True

    async def test_discover_models_excecao_interrompe_cadeia(self, monkeypatch):
        # Excecao na leitura da cadeia encerra a descoberta sem derrubar o connect

        def handler(method, address, count, slave):
            if address == 42109:
                return FakeResponse([0, 0, 0, 50])
            if address == 40000:
                return FakeResponse([1, 72])
            if address == 40074:
                raise RuntimeError("timeout modbus")
            return FakeResponse(error=True)

        fake = FakeModbusClient(handler)
        monkeypatch.setattr("drivers.fronius.driver.AsyncModbusTcpClient", fake)

        driver = FroniusDriver(make_config())
        await driver.connect()

        assert set(driver._models) == {1}
        assert driver._connected is True

    async def test_read_all_com_mppt_e_storage(self):
        def handler(method, address, count, slave):
            if address == 40002:
                return FakeResponse(common_model_regs())
            if address == 40076:
                return FakeResponse(inverter_int_regs())
            if address == 40128:
                mppt = [0] * 20
                mppt[0] = 1
                mppt[1] = 1
                mppt[2] = 3200
                mppt[3] = 80
                return FakeResponse(mppt)
            if address == 40143:
                return FakeResponse([850, 2, 0, 5000, 0, 3000, 5, 0])
            return FakeResponse(error=True)

        models = {
            1: {"address": 40000, "length": 72},
            103: {"address": 40074, "length": 50},
            160: {"address": 40126, "length": 20},
            124: {"address": 40141, "length": 8},
        }
        driver = make_driver(models=models, handler=handler)
        driver._has_storage = True

        data = await driver.read_all()

        assert data is not None
        # O modelo 160 sobrescreve os dc_inputs vindos do modelo de inversor
        assert len(data.dc_inputs) == 1
        assert data.dc_inputs[0]["voltage"] == pytest.approx(320.0)
        assert data.custom["storage"]["state_of_charge"] == pytest.approx(85.0)

    async def test_read_all_modo_inteiro(self):
        def handler(method, address, count, slave):
            if address == 40002:
                return FakeResponse(common_model_regs())
            if address == 40076:
                return FakeResponse(inverter_int_regs())
            return FakeResponse(error=True)

        models = {
            1: {"address": 40000, "length": 72},
            103: {"address": 40074, "length": 50},
        }
        driver = make_driver(models=models, handler=handler)

        data = await driver.read_all()

        assert data is not None
        assert data.manufacturer == "Fronius"
        assert data.model == "SYMO CORE 4.0"
        assert data.firmware_version == "1.2.3"
        assert data.serial_number == "SN12345"
        assert data.custom["device_generation"] == "unknown"
        assert data.ac_power == 5000.0
        assert data.ac_apparent_power == 5000.0
        assert data.ac_reactive_power == 1000.0
        assert data.ac_power_factor == 1.0
        assert data.ac_frequency == 50.0
        assert data.ac_voltage == [230.0, 230.0, 230.0]
        assert data.ac_current == [10.0, 10.0, 10.0]
        assert len(data.dc_inputs) == 1
        assert data.dc_inputs[0]["voltage"] == 320.0
        assert data.dc_inputs[0]["current"] == 8.0
        assert data.dc_inputs[0]["power"] == 2560.0
        assert data.total_energy == 10.0
        assert data.daily_energy == 500.0
        assert data.status == "running"
        assert data.operating_state == 4
        assert data.temperature == 30.0
        # eficiencia = ac_power / soma(dc_power) * 100
        assert data.efficiency == pytest.approx(5000 / 2560 * 100)
        assert driver._last_read is not None
        assert driver._consecutive_errors == 0

    async def test_read_all_modo_float(self):
        def handler(method, address, count, slave):
            if address == 40002:
                return FakeResponse(common_model_regs())
            if address == 40076:
                return FakeResponse(inverter_float_regs())
            return FakeResponse(error=True)

        models = {
            1: {"address": 40000, "length": 72},
            113: {"address": 40074, "length": 45},
        }
        driver = make_driver(models=models, handler=handler)
        driver._float_mode = True

        data = await driver.read_all()

        assert data is not None
        assert data.ac_power == pytest.approx(5000.0)
        assert data.ac_apparent_power == pytest.approx(5200.0)
        assert data.ac_reactive_power == pytest.approx(-300.0)
        assert data.ac_power_factor == pytest.approx(0.98, rel=1e-5)
        assert data.ac_frequency == pytest.approx(50.02, rel=1e-5)
        assert len(data.ac_voltage) == 3
        assert data.ac_voltage[0] == pytest.approx(230.1, rel=1e-5)
        assert data.ac_current[0] == pytest.approx(7.5)
        assert len(data.dc_inputs) == 2
        assert data.dc_inputs[0]["voltage"] == pytest.approx(380.0)
        assert data.dc_inputs[0]["current"] == pytest.approx(7.5)
        assert data.dc_inputs[1]["power"] == pytest.approx(382 * 7.3, rel=1e-5)
        assert data.total_energy == 15_000_000
        assert data.daily_energy == 25_000
        assert data.status == "running"
        assert data.operating_state == 4
        # No modo float o registrador 37 pertence a energia total
        # ([34:38]); a temperatura nao e lida nesse modo (evita o
        # valor ficticio de 1500.0 C que a sobreposicao produzia).
        assert data.temperature == 0.0
        assert data.efficiency == pytest.approx(5000 / (380 * 7.5 + 382 * 7.3) * 100)

    async def test_read_all_sem_models_retorna_none(self):
        # Sem _models definido, o proprio read_all falha e reporta erro
        driver = make_driver(models=None, handler=None)

        data = await driver.read_all()

        assert data is None
        assert driver._error_count == 1
        assert driver._consecutive_errors == 1

    async def test_read_all_inverter_model_erro(self):
        def handler(method, address, count, slave):
            if address == 40002:
                return FakeResponse(common_model_regs())
            return FakeResponse(error=True)

        models = {
            1: {"address": 40000, "length": 72},
            103: {"address": 40074, "length": 50},
        }
        driver = make_driver(models=models, handler=handler)

        data = await driver.read_all()

        assert data is not None
        assert data.ac_power == 0.0
        assert data.status == "unknown"

    @pytest.mark.parametrize("model_id,esperado", [(113, 3), (112, 2), (111, 1)])
    async def test_read_inverter_model_float_fases(self, model_id, esperado):
        def handler(method, address, count, slave):
            if address == 40002:
                return FakeResponse(inverter_float_regs())
            return FakeResponse(error=True)

        models = {model_id: {"address": 40000, "length": 45}}
        driver = make_driver(models=models, handler=handler)
        driver._float_mode = True
        data = InverterData()

        await driver._read_inverter_model(data)

        assert len(data.ac_voltage) == esperado
        assert len(data.ac_current) == esperado

    @pytest.mark.parametrize("model_id,esperado", [(103, 3), (102, 2), (101, 1)])
    async def test_read_inverter_model_inteiro_fases(self, model_id, esperado):
        def handler(method, address, count, slave):
            if address == 40002:
                return FakeResponse(inverter_int_regs())
            return FakeResponse(error=True)

        models = {model_id: {"address": 40000, "length": 50}}
        driver = make_driver(models=models, handler=handler)
        data = InverterData()

        await driver._read_inverter_model(data)

        assert len(data.ac_voltage) == esperado
        assert len(data.ac_current) == esperado
        assert data.ac_voltage[0] == 230.0

    async def test_read_inverter_model_sem_model(self):
        driver = make_driver(models={1: {"address": 40000, "length": 72}})
        data = InverterData()

        await driver._read_inverter_model(data)

        # Nenhum modelo de inversor na cadeia: dados permanecem intactos
        assert data.ac_power == 0.0
        assert data.status == "unknown"

    async def test_read_common_model_erro(self):
        driver = make_driver(
            models={1: {"address": 40000, "length": 72}},
            handler=lambda method, address, count, slave: FakeResponse(error=True)
        )
        data = InverterData()

        await driver._read_common_model(data)

        assert data.manufacturer == ""
        assert data.model == ""

    async def test_read_all_sem_common_model(self):
        def handler(method, address, count, slave):
            if address == 40076:
                return FakeResponse(inverter_int_regs())
            return FakeResponse(error=True)

        # read_all so consulta o Common Model quando o modelo 1 existe
        driver = make_driver(
            models={103: {"address": 40074, "length": 50}},
            handler=handler
        )

        data = await driver.read_all()

        assert data is not None
        assert data.model == ""
        assert data.serial_number == ""

    async def test_read_mppt_model_float(self):
        payload = [0] * 20
        payload[0] = 2
        payload[1] = 1                       # papel: PV
        payload[2], payload[3] = float_to_regs(320.0)
        payload[4], payload[5] = float_to_regs(8.0)
        payload[7] = 2                       # papel: storage
        payload[8], payload[9] = float_to_regs(300.0)
        payload[10], payload[11] = float_to_regs(5.0)

        driver = make_driver(
            models={160: {"address": 40000, "length": 20}},
            handler=lambda method, address, count, slave: FakeResponse(payload)
        )
        driver._float_mode = True
        data = InverterData()

        await driver._read_mppt_model(data)

        assert len(data.dc_inputs) == 2
        assert data.dc_inputs[0]["role"] == "pv"
        assert data.dc_inputs[0]["voltage"] == pytest.approx(320.0)
        assert data.dc_inputs[0]["current"] == pytest.approx(8.0)
        assert data.dc_inputs[0]["power"] == pytest.approx(2560.0)
        assert data.dc_inputs[1]["role"] == "storage"
        assert data.dc_inputs[1]["power"] == pytest.approx(1500.0)

    async def test_read_mppt_model_inteiro(self):
        payload = [0] * 20
        payload[0] = 2
        payload[1] = 1
        payload[2] = 3200                    # tensao -> 320.0
        payload[3] = 80                      # corrente -> 8.0
        payload[7] = 1
        payload[8] = 3100
        payload[9] = 50

        driver = make_driver(
            models={160: {"address": 40000, "length": 20}},
            handler=lambda method, address, count, slave: FakeResponse(payload)
        )
        data = InverterData()

        await driver._read_mppt_model(data)

        assert len(data.dc_inputs) == 2
        assert data.dc_inputs[0]["voltage"] == pytest.approx(320.0)
        assert data.dc_inputs[0]["current"] == pytest.approx(8.0)
        assert data.dc_inputs[1]["voltage"] == pytest.approx(310.0)

    async def test_read_mppt_model_curto_nao_add_inputs(self):
        # A guarda offset + 5 < len(registers) descarta entradas incompletas
        payload = [0] * 5
        payload[0] = 8                        # declara 8 entradas

        driver = make_driver(
            models={160: {"address": 40000, "length": 5}},
            handler=lambda method, address, count, slave: FakeResponse(payload)
        )
        data = InverterData()

        await driver._read_mppt_model(data)

        assert data.dc_inputs == []

    async def test_read_mppt_model_erro(self):
        driver = make_driver(
            models={160: {"address": 40000, "length": 20}},
            handler=lambda method, address, count, slave: FakeResponse(error=True)
        )
        data = InverterData()
        data.dc_inputs = [{"voltage": 100.0}]

        await driver._read_mppt_model(data)

        # Resposta com erro: dc_inputs preservados
        assert data.dc_inputs == [{"voltage": 100.0}]

    async def test_read_storage_model(self):
        payload = [850, 2, 0, 5000, 0, 3000, 5, 0]

        driver = make_driver(
            models={124: {"address": 40000, "length": 8}},
            handler=lambda method, address, count, slave: FakeResponse(payload)
        )
        data = InverterData()

        await driver._read_storage_model(data)

        storage = data.custom["storage"]
        assert storage["state_of_charge"] == pytest.approx(85.0)
        assert storage["charge_state"] == 2
        assert storage["charge_limit_max"] == 5000
        assert storage["discharge_limit_max"] == 3000
        assert storage["charge_limit_enable"] is True
        assert storage["discharge_limit_enable"] is False
        assert storage["grid_charge_enable"] is True

    async def test_read_storage_model_erro(self):
        driver = make_driver(
            models={124: {"address": 40000, "length": 8}},
            handler=lambda method, address, count, slave: FakeResponse(error=True)
        )
        data = InverterData()

        await driver._read_storage_model(data)

        assert "storage" not in data.custom

    async def test_get_status(self):
        def handler(method, address, count, slave):
            if address == 40002:
                return FakeResponse(common_model_regs())
            if address == 40076:
                return FakeResponse(inverter_int_regs())
            return FakeResponse(error=True)

        models = {
            1: {"address": 40000, "length": 72},
            103: {"address": 40074, "length": 50},
        }
        driver = make_driver(models=models, handler=handler)

        status = await driver.get_status()

        assert status == "running"

    async def test_get_status_sem_leitura_retorna_unknown(self):
        def handler(method, address, count, slave):
            raise RuntimeError("cliente offline")

        driver = make_driver(models={}, handler=handler)

        status = await driver.get_status()

        # Sem modelo de inverter, read_all devolve None -> unknown
        assert status == "unknown"

    async def test_get_status_excecao_retorna_error(self):
        # read_all lancando excecao inesperada e capturada pelo guard
        # de get_status (sem isso, o 'error' seria codigo morto)
        driver = make_driver(models={})

        async def falha():
            raise RuntimeError("falha simulada")

        driver.read_all = falha

        status = await driver.get_status()

        assert status == "error"

    async def test_read_register_sucesso(self):
        driver = make_driver(
            handler=lambda method, address, count, slave: FakeResponse([1, 2, 3])
        )

        values = await driver.read_register(100, count=3)

        assert values == [1, 2, 3]
        # Leitura usa a unidade configurada
        assert driver._client.calls[-1] == ("rh", 100, 3, 1)

    async def test_read_register_erro(self):
        driver = make_driver(
            handler=lambda method, address, count, slave: FakeResponse(error=True)
        )

        erro = None
        try:
            await driver.read_register(100)
        except Exception as exc:
            erro = exc

        assert erro is not None
        assert "Read error" in str(erro)

    async def test_write_register_sucesso(self):
        driver = make_driver(
            handler=lambda method, address, count, slave: FakeResponse()
        )

        assert await driver.write_register(40151, 5000) is True
        assert driver._client.calls[-1] == ("wr", 40151, 5000, 1)

    async def test_write_register_erro(self):
        driver = make_driver(
            handler=lambda method, address, count, slave: FakeResponse(error=True)
        )

        assert await driver.write_register(40151, 5000) is False

    def test_decodificadores(self, fronius_config):
        driver = FroniusDriver(fronius_config)

        # String SunSpec
        assert driver._decode_string([0x4142, 0x4300]) == "ABC"

        # Float32
        assert driver._decode_float32([]) == 0.0
        assert driver._decode_float32(float_to_regs(1.5)) == 1.5

        # Uint32
        assert driver._decode_uint32([1]) == 0
        assert driver._decode_uint32([1, 2]) == 65538

        # Uint64
        assert driver._decode_uint64([1, 2, 3]) == 0
        assert driver._decode_uint64([0, 0, 0, 7]) == 7

        # Int16 com sinal
        assert driver._decode_int16(100) == 100
        assert driver._decode_int16(65486) == -50
