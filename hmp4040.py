from __future__ import annotations

import time
from typing import Any, Dict, List


class HMP4040:
    """
    Rohde & Schwarz HMP4040 SCPI helper.

    pyvisa_instr should be a PyVISA instrument/resource object, for example:
        rm.open_resource('ASRL6::INSTR')
    """

    select_cmd_dict: Dict[str, str] = {
        "INSTrument:NSELect {0}": "Selects a channel by number",
    }

    activate_cmd_dict: Dict[str, str] = {
        "OUTPut:GENeral {0}": "Enables the outputs for all activated channels",
        "OUTPut:SELect {0}": "Activates a selected channel",
    }

    cmd_dict: Dict[str, str] = {
        "SOURce:VOLTage{0}": "Sets/Queries the voltage value of the selected channel",
        "SOURce:CURRent{0}": "Sets/Queries the current limit value of the selected channel",
        "VOLTage:PROTection:MODE{0}": "Sets/Queries the voltage protection mode, measured or protected",
        "OUTPut:STATe{0}": "Activates and enables the output for a selected channel",
    }

    query_cmd_dict: Dict[str, str] = {
        "MEASure:VOLTage?": "Measures voltage of selected channel",
        "MEASure:CURRent?": "Measures current of selected channel",
    }

    por_scpi_list: List[str] = [
        "INSTrument:NSELect 1",
        "INSTrument:NSELect 2",
        "INSTrument:NSELect 3",
        "INSTrument:NSELect 4",
        "SOURce:CURRent 0.1000",
        "SOURce:VOLTage 0.000",
        "VOLTage:PROTection:MODE measured",
        "OUTPut:STATe 0",
    ]

    def __init__(self, pyvisa_instr: Any) -> None:
        self.hmp4040 = pyvisa_instr
        self.channel_list: List[int] = [1, 2, 3, 4]

    def get_inst_state(self) -> List[str]:
        """
        Query and return a human-readable summary for each channel.
        """
        summaries: List[str] = []

        for channel in self.channel_list:
            self.hmp4040.write(f"INSTrument:NSELect {channel}")

            voltage = float(self.hmp4040.query("SOURce:VOLTage?"))
            current_lim = float(self.hmp4040.query("SOURce:CURRent?"))
            status = int(self.hmp4040.query("OUTPut:STATe?"))
            current = float(self.hmp4040.query("MEASure:CURRent?"))
            volt_prot = float(self.hmp4040.query("VOLTage:PROTection?"))
            volt_prot_active = self.hmp4040.query("VOLTage:PROTection:MODE?").strip()

            summary = (
                f"Channel {channel} voltage is {voltage:.02f} V, "
                f"overvoltage limit is {volt_prot:.02f}, "
                f"overvolt config is {volt_prot_active}, "
                f"current limit is {current_lim:.02f} A, "
                f"current is {current:.03f} A, "
                f"status is {status}"
            )
            summaries.append(summary)

        return summaries

    def get_channel_scpi_list(self, channel: int = 1) -> List[str]:
        result_list: List[str] = []

        self.hmp4040.write(f"INSTrument:NSELect {channel}")
        result_list.append(f"INSTrument:NSELect {channel}")

        for command in self.cmd_dict:
            result = self.hmp4040.query(command.format("?")).strip()
            result_list.append(command.format(f" {result}"))
            time.sleep(0.1)

        return result_list

    def get_unique_scpi_list(self) -> List[str]:
        unique_scpi_list: List[str] = []

        for channel in self.channel_list:
            channel_settings_list = self.get_channel_scpi_list(channel)
            unique_scpi_channel_list = [
                setting
                for setting in channel_settings_list
                if setting not in self.por_scpi_list
            ]

            if unique_scpi_channel_list:
                unique_scpi_list.append(channel_settings_list[0])  # channel select
                unique_scpi_list.extend(unique_scpi_channel_list)

        return unique_scpi_list


# Backward-compatible alias
hmp4040 = HMP4040
