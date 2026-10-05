"""
Unit tests for Growatt inverter driver.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.config import InverterConfig, ModbusConnection
from drivers.base import InverterData
from drivers.growatt.driver import GrowattDriver


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


def regs_str(text: str, n_regs: int) -> list[int]:
    """Converte texto em exatamente n_regs registradores ASCII."""
    padded = text.ljust(n_regs * 2, "\x00")
    if len(padded) % 2:
        padded += "\x00"
    return [(ord(padded[i]) << 8) | ord(padded[i + 1]) for i in range(0, len(padded), 2)]


def input_regs(second_string_zero=False) -> list[int]:
    """Payload dos input registers de telemetria (60 registradores)."""
    regs = [0] * 60
    regs[0] = 1                      # status: running
    regs[1], regs[2] = 0, 52000      # Ppv combinado = 5200.0 W

    # String 1
    regs[3] = 3200                   # 320.0 V
    regs[4] = 80                     # 8.0 A
    regs[5], regs[6] = 0, 25600      # 2560.0 W

    # String 2
    if second_string_zero:
        regs[7], regs[8] = 0, 0
        regs[9], regs[10] = 0, 0
    else:
        regs[7] = 3180               # 318.0 V
        regs[8] = 81                 # 8.1 A
        regs[9], regs[10] = 0, 25758  # 2575.8 W

    regs[35], regs[36] = 0, 50000    # Pac = 5000.0 W
    regs[37] = 5000                  # 50.00 Hz
    regs[38] = 2300                  # Vac L1 = 230.0 V
    regs[39] = 75                    # Iac L1 = 7.5 A
    regs[42] = 2310                  # Vac L2
    regs[43] = 76                    # Iac L2
    regs[46] = 2290                  # Vac L3
    regs[47] = 74                    # Iac L3
    regs[53], regs[54] = 0, 25000    # Eac today = 2500.0 kWh -> 2_500_000 Wh
    regs[55], regs[56] = 1, 0        # Eac total = 6553.6 kWh -> 6_553_600 Wh
    return regs


def holding_regs() -> list[int]:
    """Payload dos holding registers de configuracao (90 registradores)."""
    regs = [0] * 90
    regs[23:28] = regs_str("SN12345", 5)
    regs[88] = 0x0203                # firmware 2.3
    return regs


def make_config(unit_id=1) -> InverterConfig:
    """Configuracao valida para o driver Growatt."""
    return InverterConfig(
        id="growatt-001",
        name="Growatt MIN 5000",
        driver="growatt",
        connection=ModbusConnection(
            host="192.168.1.103",
            port=502,
            unit_id=unit_id
        )
    )


def make_driver(handler=None) -> GrowattDriver:
    """Cria o driver ja com cliente falso injetado."""
    driver = GrowattDriver(make_config())
    driver._client = FakeModbusClient(handler)
    return driver


def capability_handler(version=0x0203, soc=50, pv_voltages=(3200, 3180)):
    """Handler para a deteccao de capacidades (connect)."""

    def handler(method, address, count, slave):
        if method == "rh" and address == 88:
            return FakeResponse([version])
        if method == "ri" and address == 104:
            return FakeResponse([soc])
        if method == "ri" and 3 <= address <= 31 and (address - 3) % 4 == 0:
            idx = (address - 3) // 4
            value = pv_voltages[idx] if idx < len(pv_voltages) else 0
            return FakeResponse([value])
        return FakeResponse(error=True)

    return handler


@pytest.fixture
def growatt_config():
    return make_config()


class TestGrowattDriver:
    """Tests for GrowattDriver class."""

    def test_driver_initialization(self, growatt_config):
        driver = GrowattDriver(growatt_config)
        assert driver.config.id == "growatt-001"
        assert driver._protocol_version == 2
        assert driver._is_storage is False
        assert driver._num_mppt == 2
        assert driver._num_strings == 2
        assert driver._connected is False

    async def test_connect_sucesso_detecta_capacidades(self, monkeypatch):
        fake = FakeModbusClient(capability_handler())
        monkeypatch.setattr("drivers.growatt.driver.AsyncModbusTcpClient", fake)

        driver = GrowattDriver(make_config())
        await driver.connect()

        assert driver._connected is True
        assert driver._protocol_version == 2
        assert driver._is_storage is True
        # Vpv1 e Vpv2 com tensao, Vpv3 zerada -> 2 MPPTs
        assert driver._num_mppt == 2
        assert driver._num_strings == 2

    async def test_detect_capabilities_protocolo_3(self):
        driver = make_driver(capability_handler(version=0x0315))

        await driver._detect_capabilities()

        assert driver._protocol_version == 3

    async def test_detect_capabilities_sem_storage(self):
        # SOC > 100% invalida a leitura de bateria
        driver = make_driver(capability_handler(soc=200))

        await driver._detect_capabilities()

        assert driver._is_storage is False

    async def test_detect_capabilities_8_mppts(self):
        # Todos os 8 registradores de tensao PV com valor -> loop completo
        voltages = tuple(3000 for _ in range(8))
        driver = make_driver(capability_handler(pv_voltages=voltages))

        await driver._detect_capabilities()

        assert driver._num_mppt == 8
        assert driver._num_strings == 8

    async def test_detect_capabilities_excecao_mantem_defaults(self):
        def handler(method, address, count, slave):
            raise RuntimeError("rede indisponivel")

        driver = make_driver(handler)

        await driver._detect_capabilities()

        assert driver._protocol_version == 2
        assert driver._is_storage is False
        assert driver._num_mppt == 2

    async def test_detect_capabilities_leitura_versao_erro(self):
        def handler(method, address, count, slave):
            if method == "rh" and address == 88:
                return FakeResponse(error=True)
            if method == "ri" and address == 104:
                return FakeResponse([50])
            if method == "ri" and address == 3:
                return FakeResponse([0])
            return FakeResponse(error=True)

        driver = make_driver(handler)

        await driver._detect_capabilities()

        # Sem versao legivel mantem o padrao
        assert driver._protocol_version == 2
        assert driver._is_storage is True

    async def test_connect_falha_levanta_connection_error(self, monkeypatch):
        fake = FakeModbusClient(connect_result=False)
        monkeypatch.setattr("drivers.growatt.driver.AsyncModbusTcpClient", fake)

        driver = GrowattDriver(make_config())
        with pytest.raises(ConnectionError, match="Failed to connect to Growatt"):
            await driver.connect()

        assert driver._connected is False
        assert driver._error_count == 1

    async def test_disconnect(self, growatt_config):
        driver = GrowattDriver(growatt_config)
        client = FakeModbusClient()
        driver._client = client
        driver._connected = True

        await driver.disconnect()

        assert client.closed is True
        assert driver._connected is False

    async def test_disconnect_sem_cliente(self, growatt_config):
        driver = GrowattDriver(growatt_config)
        # Sem cliente registrado: nada a fechar
        await driver.disconnect()
        assert driver._connected is False

    async def test_read_input_registers_completo(self):
        driver = make_driver(
            lambda method, address, count, slave: FakeResponse(input_regs())
        )
        data = InverterData()

        await driver._read_input_registers(data)

        assert data.status == "running"
        assert data.operating_state == 1
        assert data.custom["pv_power"] == pytest.approx(5200.0)
        assert len(data.dc_inputs) == 2
        assert data.dc_inputs[0]["string"] == 1
        assert data.dc_inputs[0]["voltage"] == pytest.approx(320.0)
        assert data.dc_inputs[0]["current"] == pytest.approx(8.0)
        assert data.dc_inputs[0]["power"] == pytest.approx(2560.0)
        assert data.dc_inputs[1]["voltage"] == pytest.approx(318.0)
        assert data.dc_inputs[1]["current"] == pytest.approx(8.1)
        assert data.dc_inputs[1]["power"] == pytest.approx(2575.8)
        assert data.ac_power == pytest.approx(5000.0)
        assert data.ac_frequency == pytest.approx(50.0)
        assert data.ac_voltage == pytest.approx([230.0, 231.0, 229.0])
        assert data.ac_current == pytest.approx([7.5, 7.6, 7.4])
        assert data.daily_energy == pytest.approx(2_500_000.0)
        assert data.total_energy == pytest.approx(6_553_600.0)

    async def test_read_input_registers_string_zerado(self):
        driver = make_driver(
            lambda method, address, count, slave: FakeResponse(
                input_regs(second_string_zero=True)
            )
        )
        data = InverterData()

        await driver._read_input_registers(data)

        # String 2 com tensao e corrente zeradas e descartada
        assert len(data.dc_inputs) == 1

    async def test_read_input_registers_erro(self):
        driver = make_driver(
            lambda method, address, count, slave: FakeResponse(error=True)
        )
        data = InverterData()

        await driver._read_input_registers(data)

        assert data.status == "unknown"
        assert data.ac_power == 0.0

    async def test_read_holding_registers_completo(self):
        driver = make_driver(
            lambda method, address, count, slave: FakeResponse(holding_regs())
        )
        data = InverterData()

        await driver._read_holding_registers(data)

        assert data.serial_number == "SN12345"
        assert data.firmware_version == "2.3"

    async def test_read_holding_registers_erro(self):
        driver = make_driver(
            lambda method, address, count, slave: FakeResponse(error=True)
        )
        data = InverterData()

        await driver._read_holding_registers(data)

        assert data.serial_number == ""

    async def test_read_all_sucesso_com_serial_e_firmware(self):
        # _read_holding_registers le 0..88 (count=89): serial em 23-27
        # e firmware em 88. Antes o count era 30 e o acesso ao indice
        # 88 estourava IndexError, anulando o read_all inteiro.
        def handler(method, address, count, slave):
            if method == "ri":
                return FakeResponse(input_regs())
            if method == "rh" and address == 0:
                assert count == 89
                return FakeResponse(holding_regs())
            return FakeResponse(error=True)

        driver = make_driver(handler)

        data = await driver.read_all()

        assert data is not None
        assert data.serial_number == "SN12345"
        assert data.firmware_version == "2.3"
        assert driver._error_count == 0
        assert driver._consecutive_errors == 0

    async def test_read_all_falha_inesperada_retorna_none(self, monkeypatch):
        # Guard de seguranca do read_all: excecao fora dos sub-leitores
        # (aqui em _reset_errors) e capturada, conta erro e devolve None
        def handler(method, address, count, slave):
            if method == "ri":
                return FakeResponse(input_regs())
            if method == "rh" and address == 0:
                return FakeResponse(holding_regs())
            return FakeResponse(error=True)

        driver = make_driver(handler)

        def falha():
            raise RuntimeError("falha simulada")

        monkeypatch.setattr(driver, "_reset_errors", falha)

        data = await driver.read_all()

        assert data is None
        assert driver._error_count == 1

    async def test_read_all_com_is_storage_tenta_storage(self):
        # _is_storage=True: read_all chama _read_storage_data; falha
        # interna de storage nao derruba a leitura principal
        def handler(method, address, count, slave):
            if method == "ri":
                return FakeResponse(input_regs())
            if method == "rh":
                return FakeResponse(holding_regs())
            return FakeResponse(error=True)

        driver = make_driver(handler)
        driver._is_storage = True

        data = await driver.read_all()

        assert data is not None
        assert data.serial_number == "SN12345"

    @pytest.mark.parametrize("status_code,esperado", [
        (0, "waiting"),
        (1, "running"),
        (3, "fault"),
        (2, "unknown"),
    ])
    async def test_get_status(self, status_code, esperado):
        driver = make_driver(
            lambda method, address, count, slave: FakeResponse([status_code])
        )

        assert await driver.get_status() == esperado

    async def test_get_status_resposta_erro(self):
        driver = make_driver(
            lambda method, address, count, slave: FakeResponse(error=True)
        )

        assert await driver.get_status() == "error"

    async def test_get_status_excecao(self):
        def handler(method, address, count, slave):
            raise RuntimeError("cliente offline")

        driver = make_driver(handler)

        assert await driver.get_status() == "error"

    async def test_read_register_sucesso(self):
        driver = make_driver(
            lambda method, address, count, slave: FakeResponse([7, 8])
        )

        values = await driver.read_register(10, count=2)

        assert values == [7, 8]
        assert driver._client.calls[-1] == ("rh", 10, 2, 1)

    async def test_read_register_erro(self):
        driver = make_driver(
            lambda method, address, count, slave: FakeResponse(error=True)
        )

        erro = None
        try:
            await driver.read_register(10)
        except Exception as exc:
            erro = exc

        assert erro is not None
        assert "Read error" in str(erro)

    async def test_write_register_sucesso(self):
        driver = make_driver(lambda method, address, count, slave: FakeResponse())

        assert await driver.write_register(100, 42) is True
        assert driver._client.calls[-1] == ("wr", 100, 42, 1)

    async def test_write_register_erro(self):
        driver = make_driver(
            lambda method, address, count, slave: FakeResponse(error=True)
        )

        assert await driver.write_register(100, 42) is False

    async def test_set_time_slot_sem_storage(self):
        driver = make_driver(lambda method, address, count, slave: FakeResponse())

        resultado = await driver.set_time_slot(
            0, "08:00", "20:00", "load", True
        )

        assert resultado is False
        assert driver._client.calls == []

    async def test_set_time_slot_sucesso(self):
        driver = make_driver(lambda method, address, count, slave: FakeResponse())
        driver._is_storage = True

        resultado = await driver.set_time_slot(
            2, "07:15", "22:45", "grid", False
        )

        assert resultado is True
        escritas = [(addr, value) for method, addr, value, _ in driver._client.calls]
        # base = 3100 + slot * 6
        assert escritas == [
            (3112, 435),   # inicio 07:15 -> 435 min
            (3113, 1365),  # fim 22:45 -> 1365 min
            (3114, 2),     # prioridade "grid" -> 2
            (3115, 0),     # desabilitado -> 0
        ]

    async def test_set_time_slot_prioridade_desconhecida(self):
        driver = make_driver(lambda method, address, count, slave: FakeResponse())
        driver._is_storage = True

        resultado = await driver.set_time_slot(
            0, "00:00", "23:59", "indefinida", True
        )

        assert resultado is True
        escritas = [(addr, value) for method, addr, value, _ in driver._client.calls]
        # Prioridade fora do mapa vira 0 (load)
        assert escritas == [
            (3100, 0),
            (3101, 1439),
            (3102, 0),
            (3103, 1),
        ]

    async def test_set_time_slot_excecao_na_escrita(self):
        def handler(method, address, count, slave):
            raise OSError("registro somente leitura")

        driver = make_driver(handler)
        driver._is_storage = True

        resultado = await driver.set_time_slot(
            0, "08:00", "20:00", "battery", True
        )

        assert resultado is False

    @pytest.mark.parametrize("soc,esperado,modo", [
        (50, 50, "charging"),
        (0, 0, "idle"),
        (80, 80, "discharging"),
        (30, 30, "fault"),
    ])
    async def test_read_storage_data(self, soc, esperado, modo):
        battery_status = {
            "idle": 0,
            "charging": 1,
            "discharging": 2,
            "fault": 3,
        }[modo]

        def handler(method, address, count, slave):
            if method == "ri" and address == 104:
                return FakeResponse([soc])
            if method == "ri" and address == 105:
                # tensao, corrente, potencia (H/L), status
                return FakeResponse([530, 65500, 0, 2500, battery_status])
            # REG_BATTERY_CHARGE_LIMIT = 951 (4 registradores: 951-954)
            if method == "rh" and address == 951:
                return FakeResponse([0, 1000, 0, 2000])
            return FakeResponse(error=True)

        driver = make_driver(handler)
        data = InverterData()

        await driver._read_storage_data(data)

        storage = data.custom["storage"]
        assert storage["state_of_charge"] == esperado
        assert storage["voltage"] == pytest.approx(53.0)
        assert storage["current"] == pytest.approx(-3.6)
        assert storage["power"] == pytest.approx(250.0)
        assert storage["mode"] == modo
        assert storage["charge_limit"] == 1000
        assert storage["discharge_limit"] == 2000

    async def test_read_storage_data_leitura_soc_erro(self):
        def handler(method, address, count, slave):
            if method == "ri" and address == 104:
                return FakeResponse(error=True)
            if method == "ri" and address == 105:
                return FakeResponse([530, 65500, 0, 2500, 1])
            if method == "rh" and address == 951:
                return FakeResponse([0, 1000, 0, 2000])
            return FakeResponse(error=True)

        driver = make_driver(handler)
        data = InverterData()

        # Sem o dict 'storage', a escrita dos limites gera KeyError que e
        # engolido pelo except do proprio metodo.
        await driver._read_storage_data(data)

        assert "storage" not in data.custom

    async def test_read_all_todas_leituras_erro(self):
        driver = make_driver(
            lambda method, address, count, slave: FakeResponse(error=True)
        )
        data = await driver.read_all()

        # Todas as leituras retornam erro: read_all devolve dados zerados
        assert data is not None
        assert data.status == "unknown"
        assert driver._is_storage is False
        assert driver._last_read is not None

    def test_decodificadores(self, growatt_config):
        driver = GrowattDriver(growatt_config)

        # ASCII: bytes fora da faixa imprimivel sao ignorados
        assert driver._decode_ascii([0x534E, 0x0001, 0x4344]) == "SNCD"

        # Int16 com sinal
        assert driver._decode_int16(100) == 100
        assert driver._decode_int16(65436) == -100

        # Int32 com sinal
        assert driver._decode_int32([0, 1000]) == 1000
        assert driver._decode_int32([0xFFFF, 0xFFFF]) == -1
        assert driver._decode_int32([0x8000, 0]) == -2147483648
        assert driver._decode_int32([1]) == 0
