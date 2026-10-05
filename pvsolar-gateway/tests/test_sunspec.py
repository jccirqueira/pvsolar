"""
Unit tests for SunSpec inverter driver.
"""

import struct
import sys
from pathlib import Path

import pytest
from pymodbus.exceptions import ModbusException

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.config import InverterConfig, ModbusConnection
from drivers.base import InverterData
from drivers.sunspec.driver import SunSpecDriver


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
        regs_str("TestCorp", 16)
        + regs_str("INV-3PH", 16)
        + regs_str("OPTION", 16)
        + regs_str("9.8.7", 8)
        + regs_str("SS123456", 16)
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
    # O registrador 37 pertence ao uint64 de energia total ([34:38]) mas
    # tambem e lido como temperatura pelo codigo (mesma sobreposicao do
    # driver Fronius).
    regs[37] = 15000
    regs[38], regs[39] = 0, 25
    return regs


def make_config(unit_id=1) -> InverterConfig:
    """Configuracao valida para o driver SunSpec."""
    return InverterConfig(
        id="sunspec-001",
        name="Inversor SunSpec",
        driver="sunspec",
        connection=ModbusConnection(
            host="192.168.1.105",
            port=502,
            unit_id=unit_id
        )
    )


def make_driver(models=None, handler=None) -> SunSpecDriver:
    """Cria o driver ja com cliente falso injetado."""
    driver = SunSpecDriver(make_config())
    driver._client = FakeModbusClient(handler)
    if models is not None:
        driver._models = models
    return driver


def chain_handler(chain):
    """Handler que serve uma cadeia de modelos SunSpec.

    `chain` e um dict endereco -> [model_id, length].
    """

    def handler(method, address, count, slave):
        if address in chain:
            return FakeResponse(chain[address])
        return FakeResponse(error=True)

    return handler


@pytest.fixture
def sunspec_config():
    return make_config()


class TestSunSpecDriver:
    """Tests for SunSpecDriver class."""

    def test_driver_initialization(self, sunspec_config):
        driver = SunSpecDriver(sunspec_config)
        assert driver.config.id == "sunspec-001"
        assert driver._models == {}
        assert driver._model_chain == []
        assert driver._float_mode is False
        assert driver._connected is False

    async def test_connect_sucesso_descobre_cadeia(self, monkeypatch):
        chain = {
            40000: [1, 72],
            40074: [103, 50],
            40126: [160, 13],
            40141: [124, 8],
            40151: [0xFFFF, 0],
        }
        fake = FakeModbusClient(chain_handler(chain))
        monkeypatch.setattr("drivers.sunspec.driver.AsyncModbusTcpClient", fake)

        driver = SunSpecDriver(make_config())
        await driver.connect()

        assert driver._connected is True
        assert driver._model_chain == [1, 103, 160, 124]
        assert driver._models[1] == {"address": 40000, "length": 72}
        assert driver._float_mode is False

    async def test_connect_sucesso_ativa_float_mode(self, monkeypatch):
        chain = {
            40000: [1, 72],
            40074: [113, 45],
            40121: [0xFFFF, 0],
        }
        fake = FakeModbusClient(chain_handler(chain))
        monkeypatch.setattr("drivers.sunspec.driver.AsyncModbusTcpClient", fake)

        driver = SunSpecDriver(make_config())
        await driver.connect()

        assert driver._model_chain == [1, 113]
        assert driver._float_mode is True

    async def test_connect_falha_levanta_connection_error(self, monkeypatch):
        fake = FakeModbusClient(connect_result=False)
        monkeypatch.setattr("drivers.sunspec.driver.AsyncModbusTcpClient", fake)

        driver = SunSpecDriver(make_config())
        with pytest.raises(ConnectionError, match="Failed to connect to"):
            await driver.connect()

        assert driver._connected is False
        assert driver._error_count == 1

    async def test_disconnect(self, sunspec_config):
        driver = SunSpecDriver(sunspec_config)
        client = FakeModbusClient()
        driver._client = client
        driver._connected = True

        await driver.disconnect()

        assert client.closed is True
        assert driver._connected is False

    async def test_disconnect_sem_cliente(self, sunspec_config):
        driver = SunSpecDriver(sunspec_config)
        # Sem cliente registrado: nada a fechar
        await driver.disconnect()
        assert driver._connected is False

    async def test_discover_models_excecao_interrompe(self, monkeypatch):
        def handler(method, address, count, slave):
            if address == 40000:
                raise RuntimeError("timeout modbus")
            return FakeResponse(error=True)

        fake = FakeModbusClient(handler)
        monkeypatch.setattr("drivers.sunspec.driver.AsyncModbusTcpClient", fake)

        driver = SunSpecDriver(make_config())
        await driver.connect()

        # A excecao encerra a descoberta sem derrubar o connect
        assert driver._models == {}
        assert driver._model_chain == []
        assert driver._connected is True

    async def test_discover_models_resposta_erro_interrompe(self, monkeypatch):
        fake = FakeModbusClient(lambda method, address, count, slave: FakeResponse(error=True))
        monkeypatch.setattr("drivers.sunspec.driver.AsyncModbusTcpClient", fake)

        driver = SunSpecDriver(make_config())
        await driver.connect()

        assert driver._model_chain == []
        assert driver._float_mode is False

    async def test_read_all_completo(self):
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
        assert data.inverter_id == "sunspec-001"
        assert data.manufacturer == "TestCorp"
        assert data.model == "INV-3PH"
        assert data.firmware_version == "9.8.7"
        assert data.serial_number == "SS123456"
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
        assert data.total_energy == 10.0
        assert data.daily_energy == 500.0
        assert data.status == "running"
        assert data.operating_state == 4
        assert data.temperature == 30.0
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

        data = await driver.read_all()

        assert data is not None
        assert data.ac_power == pytest.approx(5000.0)
        assert data.ac_power_factor == pytest.approx(0.98, rel=1e-5)
        assert len(data.ac_voltage) == 3
        assert len(data.dc_inputs) == 2
        assert data.total_energy == 15_000_000
        assert data.daily_energy == 25_000
        assert data.status == "running"
        # No modo float o registrador 37 pertence a energia total
        # ([34:38]); a temperatura nao e lida nesse modo (evita o
        # valor ficticio de 1500.0 C que a sobreposicao produzia)
        assert data.temperature == 0.0

    async def test_read_all_com_storage(self):
        def handler(method, address, count, slave):
            if address == 40002:
                return FakeResponse(common_model_regs())
            if address == 40076:
                return FakeResponse(inverter_int_regs())
            if address == 40143:
                return FakeResponse([850, 2, 0, 5000, 0, 3000])
            return FakeResponse(error=True)

        models = {
            1: {"address": 40000, "length": 72},
            103: {"address": 40074, "length": 50},
            124: {"address": 40141, "length": 8},
        }
        driver = make_driver(models=models, handler=handler)

        data = await driver.read_all()

        assert data is not None
        storage = data.custom["storage"]
        assert storage["state_of_charge"] == pytest.approx(85.0)
        assert storage["charge_state"] == 2
        assert storage["charge_limit"] == 5000
        assert storage["discharge_limit"] == 3000

    async def test_read_all_com_mppt_preenche_dc_inputs(self):
        # _read_mppt_model decodifica tensao/corrente (uint16) e
        # potencia (uint32) por MPPT, escala 0.1
        def handler(method, address, count, slave):
            if address == 40002:
                return FakeResponse(common_model_regs())
            if address == 40076:
                return FakeResponse(inverter_int_regs())
            if address == 40128:
                payload = [0] * 13
                payload[0] = 2            # 2 MPPTs
                payload[1] = 3200         # MPPT1: tensao 320.0 V
                payload[2] = 80           # MPPT1: corrente 8.0 A
                payload[4] = 100          # MPPT1: potencia 10.0 W (H=0, L=100)
                payload[5] = 3100         # MPPT2: tensao 310.0 V
                payload[6] = 70           # MPPT2: corrente 7.0 A
                payload[8] = 50           # MPPT2: potencia 5.0 W (H=0, L=50)
                return FakeResponse(payload)
            return FakeResponse(error=True)

        models = {
            1: {"address": 40000, "length": 72},
            103: {"address": 40074, "length": 50},
            160: {"address": 40126, "length": 13},
        }
        driver = make_driver(models=models, handler=handler)

        data = await driver.read_all()

        assert data is not None
        assert len(data.dc_inputs) == 2
        assert data.dc_inputs[0] == {
            "mppt": 1, "voltage": 320.0, "current": 8.0, "power": 10.0
        }
        assert data.dc_inputs[1] == {
            "mppt": 2, "voltage": 310.0, "current": 7.0, "power": 5.0
        }

    async def test_read_all_sem_modelos_retorna_none(self):
        # Sem modelo de inverter (101-113) descoberto: nada a ler ->
        # None + erro reportado (em vez de InverterData zerada)
        driver = make_driver()

        data = await driver.read_all()

        assert data is None
        assert driver._error_count == 1

    async def test_read_all_falha_inesperada_retorna_none(self, monkeypatch):
        # Guard de seguranca do read_all: excecao fora dos sub-leitores
        # (aqui em _reset_errors) e capturada, conta erro e devolve None
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

        def falha():
            raise RuntimeError("falha simulada")

        monkeypatch.setattr(driver, "_reset_errors", falha)

        data = await driver.read_all()

        assert data is None
        assert driver._error_count == 1

    async def test_read_all_sem_common_model(self):
        def handler(method, address, count, slave):
            if address == 40076:
                return FakeResponse(inverter_int_regs())
            return FakeResponse(error=True)

        driver = make_driver(
            models={103: {"address": 40074, "length": 50}},
            handler=handler
        )

        data = await driver.read_all()

        assert data is not None
        assert data.manufacturer == ""
        assert data.ac_power == 5000.0

    async def test_read_all_sem_inverter_model(self):
        # Apenas o common model: sem modelo de inverter nao ha medidas
        # -> None + erro reportado (em vez de InverterData zerada)
        driver = make_driver(
            models={1: {"address": 40000, "length": 72}},
            handler=lambda method, address, count, slave: FakeResponse(
                common_model_regs()
            )
        )

        data = await driver.read_all()

        assert data is None
        assert driver._error_count == 1

    @pytest.mark.parametrize("model_id,esperado", [(113, 3), (112, 2), (111, 1)])
    async def test_read_inverter_model_float_fases(self, model_id, esperado):
        def handler(method, address, count, slave):
            if address == 40002:
                return FakeResponse(inverter_float_regs())
            return FakeResponse(error=True)

        driver = make_driver(
            models={model_id: {"address": 40000, "length": 45}},
            handler=handler
        )
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

        driver = make_driver(
            models={model_id: {"address": 40000, "length": 50}},
            handler=handler
        )
        data = InverterData()

        await driver._read_inverter_model(data)

        assert len(data.ac_voltage) == esperado
        assert data.ac_voltage[0] == 230.0

    async def test_read_inverter_model_erro(self):
        driver = make_driver(
            models={103: {"address": 40000, "length": 50}},
            handler=lambda method, address, count, slave: FakeResponse(error=True)
        )
        data = InverterData()

        await driver._read_inverter_model(data)

        assert data.ac_power == 0.0

    async def test_read_common_model_erro(self):
        driver = make_driver(
            models={1: {"address": 40000, "length": 72}},
            handler=lambda method, address, count, slave: FakeResponse(error=True)
        )
        data = InverterData()

        await driver._read_common_model(data)

        assert data.manufacturer == ""
        assert data.serial_number == ""

    async def test_read_mppt_model_erro_preserva_dc_inputs(self):
        driver = make_driver(
            models={160: {"address": 40000, "length": 13}},
            handler=lambda method, address, count, slave: FakeResponse(error=True)
        )
        data = InverterData()
        data.dc_inputs = [{"voltage": 100.0}]

        await driver._read_mppt_model(data)

        assert data.dc_inputs == [{"voltage": 100.0}]

    async def test_read_storage_model_erro(self):
        driver = make_driver(
            models={124: {"address": 40000, "length": 8}},
            handler=lambda method, address, count, slave: FakeResponse(error=True)
        )
        data = InverterData()

        await driver._read_storage_model(data)

        assert "storage" not in data.custom

    async def test_get_status_retorna_status(self):
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

        assert await driver.get_status() == "running"

    async def test_get_status_retorna_unknown_quando_sem_dados(self):
        driver = make_driver()

        async def sem_dados():
            return None

        driver.read_all = sem_dados

        assert await driver.get_status() == "unknown"

    async def test_get_status_retorna_error_quando_falha(self):
        driver = make_driver()

        async def falha():
            raise RuntimeError("falha simulada")

        driver.read_all = falha

        assert await driver.get_status() == "error"

    async def test_read_register_sucesso(self):
        driver = make_driver(
            handler=lambda method, address, count, slave: FakeResponse([4, 5])
        )

        values = await driver.read_register(40000, count=2)

        assert values == [4, 5]
        assert driver._client.calls[-1] == ("rh", 40000, 2, 1)

    async def test_read_register_erro_levanta_modbus_exception(self):
        driver = make_driver(
            handler=lambda method, address, count, slave: FakeResponse(error=True)
        )

        with pytest.raises(ModbusException, match="Read error"):
            await driver.read_register(40000)

    async def test_write_register_sucesso(self):
        driver = make_driver(handler=lambda method, address, count, slave: FakeResponse())

        assert await driver.write_register(40151, 5000) is True
        assert driver._client.calls[-1] == ("wr", 40151, 5000, 1)

    async def test_write_register_erro(self):
        driver = make_driver(
            handler=lambda method, address, count, slave: FakeResponse(error=True)
        )

        assert await driver.write_register(40151, 5000) is False

    def test_decodificadores(self, sunspec_config):
        driver = SunSpecDriver(sunspec_config)

        # String SunSpec
        assert driver._decode_string([0x5375, 0x6E00]) == "Sun"

        # Float32
        assert driver._decode_float32([1]) == 0.0
        assert driver._decode_float32(float_to_regs(2.75)) == 2.75

        # Uint32
        assert driver._decode_uint32([0]) == 0
        assert driver._decode_uint32([0x0001, 0x0002]) == 65538

        # Uint64
        assert driver._decode_uint64([0, 0, 0]) == 0
        assert driver._decode_uint64([0, 0, 0, 42]) == 42

        # Int16 com sinal
        assert driver._decode_int16(100) == 100
        assert driver._decode_int16(65535) == -1


class TestSunSpecGuardsDeExcecao:
    """Guards dos sub-leitores: excecao do cliente Modbus e engolida e logada."""

    async def test_read_common_model_excecao_engolida(self):
        def handler(method, address, count, slave):
            if address == 40002:
                raise RuntimeError("timeout modbus")
            return FakeResponse(error=True)

        driver = make_driver(
            models={1: {"address": 40000, "length": 72}},
            handler=handler
        )
        data = InverterData()

        await driver._read_common_model(data)

        # a excecao nao propaga e os campos ficam intactos
        assert data.manufacturer == ""
        assert data.model == ""

    async def test_read_inverter_model_sem_modelo_retorna_sem_leitura(self):
        # nenhum modelo 101-113 na cadeia: sai antes de tocar no cliente
        driver = make_driver(
            models={1: {"address": 40000, "length": 72}},
            handler=lambda method, address, count, slave: FakeResponse(
                common_model_regs()
            )
        )
        data = InverterData()

        await driver._read_inverter_model(data)

        assert data.ac_power == 0.0
        assert driver._client.calls == []

    async def test_read_inverter_model_excecao_engolida(self):
        def handler(method, address, count, slave):
            if address == 40076:
                raise RuntimeError("timeout modbus")
            return FakeResponse(error=True)

        driver = make_driver(
            models={103: {"address": 40074, "length": 50}},
            handler=handler
        )
        data = InverterData()

        await driver._read_inverter_model(data)

        assert data.ac_power == 0.0
        assert data.status == "unknown"

    async def test_read_mppt_model_excecao_engolida(self):
        def handler(method, address, count, slave):
            raise RuntimeError("timeout modbus")

        driver = make_driver(
            models={160: {"address": 40000, "length": 13}},
            handler=handler
        )
        data = InverterData()
        data.dc_inputs = [{"voltage": 100.0}]

        await driver._read_mppt_model(data)

        # a falha no cliente preserva o estado anterior de dc_inputs
        assert data.dc_inputs == [{"voltage": 100.0}]

    async def test_read_storage_model_excecao_engolida(self):
        def handler(method, address, count, slave):
            raise RuntimeError("timeout modbus")

        driver = make_driver(
            models={124: {"address": 40000, "length": 8}},
            handler=handler
        )
        data = InverterData()

        await driver._read_storage_model(data)

        assert "storage" not in data.custom
