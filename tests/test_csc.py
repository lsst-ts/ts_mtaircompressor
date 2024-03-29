import pathlib
import typing
import unittest

from lsst.ts import mtaircompressor, salobj

CONFIG_DIR = pathlib.Path(__file__).parent / "data" / "config"


class MTAirCompressorCscTestCase(
    salobj.BaseCscTestCase, unittest.IsolatedAsyncioTestCase
):
    def basic_make_csc(
        self,
        initial_state: salobj.State,
        config_dir: str,
        simulation_mode: int,
        index: int = 1,
        **kwargs: typing.Any,
    ) -> None:
        return mtaircompressor.MTAirCompressorCsc(
            index,
            initial_state=initial_state,
            config_dir=CONFIG_DIR,
            simulation_mode=1,
        )

    async def test_standard_state_transitions(self) -> None:
        async with self.make_csc(index=2, initial_state=salobj.State.STANDBY):
            await self.check_standard_state_transitions(
                enabled_commands=["powerOn", "powerOff", "reset"]
            )

    async def test_bin_script(self) -> None:
        await self.check_bin_script(
            name="MTAirCompressor",
            exe_name="run_mtaircompressor",
            index=1,
        )
        await self.check_bin_script(
            name="MTAirCompressor",
            exe_name="run_mtaircompressor",
            index=2,
        )
