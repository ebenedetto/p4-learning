from p4utils.utils.topology import Topology
from p4utils.utils.sswitch_API import *
from crc import Crc
import socket, struct, pickle, os

crc32_polinomials = [0x04C11DB7, 0xEDB88320, 0xDB710641, 0x82608EDB, 0x741B8CD7, 0xEB31D82E,
                     0xD663B05, 0xBA0DC66B, 0x32583499, 0x992C1A4C, 0x32583499, 0x992C1A4C]


class CMSController(object):

    def __init__(self, sw_name):

        self.topo = Topology(db="topology.db")
        self.sw_name = sw_name
        self.thrift_port = self.topo.get_thrift_port(sw_name)
        self.controller = SimpleSwitchAPI(self.thrift_port)

        self.custom_calcs = self.controller.get_custom_crc_calcs()
        self.register_num =  len(self.custom_calcs)

        self.init()
        self.registers = []

    def init(self):
        self.set_crc_custom_hashes()
        self.create_hashes()
        #self.set_forwarding()

    def set_forwarding(self):
        self.controller.table_add("forwarding", "set_egress_port", ['1'], ['2'])
        self.controller.table_add("forwarding", "set_egress_port", ['2'], ['1'])

    def reset_registers(self):
        for i in range(self.register_num):
            self.controller.register_reset("sketch{}".format(i))

    def flow_to_bytestream(self, flow):
        return socket.inet_aton(flow[0]) + socket.inet_aton(flow[1]) + struct.pack(">HHB",flow[2], flow[3], 6)

    def set_crc_custom_hashes(self):
        i = 0
        for custom_crc32, width in sorted(self.custom_calcs.items()):
            self.controller.set_crc32_parameters(custom_crc32, crc32_polinomials[i], 0xffffffff, 0xffffffff, True, True)
            i+=1

    def create_hashes(self):
        self.hashes = []
        for i in range(self.register_num):
            self.hashes.append(Crc(32, crc32_polinomials[i], True, 0xffffffff, True, 0xffffffff))

    def read_registers(self):
        self.registers = []
        for i in range(self.register_num):
            self.registers.append(self.controller.register_read("sketch{}".format(i)))

    def get_cms(self, flow, mod):
        values = []
        for i in range(self.register_num):
            index = self.hashes[i].bit_by_bit_fast((self.flow_to_bytestream(flow))) % mod
            values.append(self.registers[i][index])
        return min(values)

    def decode_registers(self, eps, n, mod, ground_truth_file="sent_flows.pickle"):

        """In the decoding function you were free to compute whatever you wanted.
           This solution includes a very basic statistic, with the number of flows inside the confidence bound.
        """
        self.read_registers()
        confidence_count = 0
        flows = pickle.load(open(ground_truth_file, "r"))
        for flow, n_packets in flows.items():
            cms = self.get_cms(flow, mod)
            if not (cms <(n_packets + (eps*n))):
                confidence_count +=1

        print "Not hold for {}%".format(float(confidence_count)/len(flows)*100)


if __name__ == "__main__":

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--sw', type=str, required=False, default="s1")
    parser.add_argument('--eps', type=float, required=False, default=0.01)
    parser.add_argument('--n', type=int, required=False, default=1000)
    parser.add_argument('--mod', type=int, required=False, default=4096)
    parser.add_argument('--flow-file', type=str, required=False, default="sent_flows.pickle")
    args = parser.parse_args()


    controller = CMSController(args.sw)
    #controller.decode_registers(args.eps, args.n, args.mod, args.flow_file)
