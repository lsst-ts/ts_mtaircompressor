# This file is part of ts_mtaircompressor.
#
# Developed for the Vera Rubin Observatory Telescope and Site Systems.
# This product includes software developed by the LSST Project
# (https://www.lsst.org).
# See the COPYRIGHT file at the top-level directory of this distribution
# for details of code ownership.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

__all__ = ["create_server", "create_server_and_run_on_background"]

import asyncio
import socket

from pymodbus.server import ModbusTcpServer
from pymodbus.simulator import DataType, SimData, SimDevice

from .aircompressor_model import Register


def create_server() -> ModbusTcpServer:
    """Create simulator server. Uses arbitrary constants for values, please
    consult Delcos XL register map - see Register enum.

    Returns
    -------
    server : `ModbusTcpServer`
        Created server instance.
    """
    # 1. Define the initial data block using SimData
    sim_data = [
        SimData(address=Register.WATER_LEVEL, values=list(range(2, 20)), datatype=DataType.REGISTERS),
        SimData(address=Register.STATUS, values=[0x01, 0x00, 0x01], datatype=DataType.REGISTERS),
        SimData(address=Register.ERROR_E400, values=list(range(100, 116)), datatype=DataType.REGISTERS),
        SimData(
            address=Register.SOFTWARE_VERSION,
            values="LSST Test Compressor 42",
            count=2,
            datatype=DataType.STRING,
        ),
        SimData(address=Register.SERIAL_NUMER, values="v0.0.0", count=2, datatype=DataType.STRING),
        SimData(address=Register.REMOTE_CMD, values=0, count=1, datatype=DataType.REGISTERS),
        SimData(address=Register.RESET, values=0, count=1, datatype=DataType.REGISTERS),
    ]

    # We need a reference to the server inside the callback to update secondary
    # registers.  A mutable list allows us to inject the server instance after
    # it is instantiated.
    server_ref: list[ModbusTcpServer] = []

    # 2. Use the SimDevice `action` callback to intercept writes
    async def intercept_remote_cmd(
        device_id: int,
        func_code: int,
        address: int,
        count: int,
        old_values: list[int],
        new_values: list[int] | list[bool] | None,
    ) -> None:
        # new_values is only populated on write requests.
        if new_values is not None and address == Register.REMOTE_CMD:
            val = new_values[0]
            status_val = [0x02] if val == 0xFF01 else [0x01]
            inhibit_val = [0x00] if val == 0xFF01 else [0x01]

            if server_ref:
                srv = server_ref[0]
                # Update the side-effect registers.
                # Function code 3 is typically used to represent holding
                # registers internally.
                await srv.async_setValues(device_id, 3, Register.STATUS, status_val)
                await srv.async_setValues(device_id, 3, Register.INHIBIT, inhibit_val)

    sim_device = SimDevice(id=0, simdata=sim_data, action=intercept_remote_cmd)

    # 4. ModbusTcpServer can now take a SimDevice directly as its context
    server = ModbusTcpServer(context=sim_device)
    server_ref.append(server)

    return server


async def create_server_and_run_on_background() -> tuple[
    ModbusTcpServer,
    asyncio.Task,
    str,
    int,
]:
    """Create and run simulator on background.

    Returns
    -------
    server : `ModbusTcpServer`
        Created server instance.
    task: `asyncio.Task`
        Task running the server.
    host: `str`
        Created server IP.
    port: `int`
        Created server port number.
    """
    server = create_server()

    # make sure socket is created and listen for incoming connection, so we can
    # get its address
    await server.listen()

    simulator_task = asyncio.create_task(server.serve_forever())
    # the resulting object shall be asyncio.SocketTransport
    st = [s for s in server.transport.sockets if s.family == socket.AF_INET][0]
    if st is None:
        raise RuntimeError(
            "The simulator cannot get data of any connected socket. Most likely "
            "the previous tests failed, leaving simulator server listening for "
            "the incoming connections."
        )
    host, port = socket.getnameinfo(st.getsockname(), socket.NI_NUMERICSERV)
    return server, simulator_task, host, int(port)
