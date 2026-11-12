import argparse
import time
import pyvisa
from hmp4040 import HMP4040


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="10.42.0.232")
    parser.add_argument("--port", type=int, default=5025)
    args = parser.parse_args()

    rm = pyvisa.ResourceManager()

    resource = f"TCPIP::{args.host}::{args.port}::SOCKET"
    hmp4040_ps = rm.open_resource(resource)
    hmp4040_ps.timeout = 3000
    hmp4040_ps.read_termination = "\n"
    hmp4040_ps.write_termination = "\n"

    print(hmp4040_ps.query("*IDN?"))

    ps = HMP4040(pyvisa_instr=hmp4040_ps)

    current_setting_list = ps.get_unique_scpi_list()

    hmp4040_ps.write("*RST")
    time.sleep(2)

    for scpi_cmd in current_setting_list:
        hmp4040_ps.write(scpi_cmd)

    time.sleep(2)

    for line in ps.get_inst_state():
        print(line)


if __name__ == "__main__":
    main()
