#! /usr/bin/env python

from tenhou_log_utils.io import load_mjlog
from tenhou_log_utils.parser import parse_mjlog
import numpy as np
import copy

MAX_PAI_NUMBER = 136

mjlog_file = 'hoge.mjlog'
import sys
mjlog_file = sys.argv[1]

mjdata_dict = parse_mjlog(load_mjlog(mjlog_file))
meta_data = mjdata_dict['meta']

player_rate = [float(player['rate']) for player in meta_data['UN']]
rule_set = meta_data['GO']['config']

class RoundSimulator():
    def __init__(self, player_rate=None):
        self.player_rate = player_rate
        self.dora_indicator = []
        self.leader = np.zeros(4, dtype=bool)
        self.pai_open = np.zeros(MAX_PAI_NUMBER+1, dtype=bool)
        self.kyokumen_list = []
        self.player_last_draw = -1
        self.player_last_discard = -1
        self.player_reach_step = [0, 0, 0, 0]
        self.player_online = [True, True, True, True]
        return
    
    def parse_init(self, data):
        self.leader[int(data['oya'])] = True
        self.scores = data['scores']
        self.hands = data['hands']
        self.melds = [[], [], [], []]
        self.info = {
            'round': int(data['round']),
            'combo' : int(data['combo']),
            'reach': int(data['reach']),
            }
        self.dora_indicator.append(int(data['dora']))
        self.pai_open[self.dora_indicator] = True

    def update_datalist(self, player, discard_pai, is_tsumo_giri):
        kyokumen = {
            'player': player,
            'discard': discard_pai,
            'is_tsumo_giri': is_tsumo_giri,
            'riich_steps': list(self.player_reach_step),
            'online': list(self.player_online),
            'oya': list(self.leader),
            'dora_indicator': list(self.dora_indicator),
            'scores': list(self.scores),
            'info': copy.deepcopy(self.info),
            'hands': copy.deepcopy(self.hands),
            'melds': copy.deepcopy(self.melds),
        }
        self.kyokumen_list.append(kyokumen)

    def parse_action(self, tag, data):
        if tag == 'DISCARD':
            player = int(data['player'])
            tile = int(data['tile'])
            num_skip = 0 if self.player_last_discard == -1 else (player - self.player_last_discard) % 4 - 1 
            for _ in range(num_skip):
                self.update_datalist(-1, MAX_PAI_NUMBER, False)
            is_tsumo_giri = (self.player_last_draw == player) and (self.hands[player][-1] == tile)
            self.hands[player] = [i for i in self.hands[player] if i != tile]
            self.update_datalist(player, tile, is_tsumo_giri)
            self.player_last_discard = player
        if tag == 'DRAW':
            player = int(data['player'])
            tile = int(data['tile'])
            self.hands[player].append(tile)
            self.player_last_draw = player
        if tag == 'CALL':
            caller = int(data['caller'])
            callee = int(data['callee'])
            mentsu = data['mentsu']
            call_type = data['call_type']
            if call_type == 'AnKan':
                mentsu = list(range(mentsu[0], mentsu[0]+4))
            if call_type == 'KaKan':
                self.melds[caller] = [m for m in self.melds[caller] if not set(m) <= set(mentsu)]
            self.melds[caller].append(mentsu)
            self.hands[caller] = [i for i in self.hands[caller] if not i in mentsu]
        if tag == 'REACH':
            player = int(data['player'])
            step = int(data['step'])
            self.player_reach_step[player] = step
            if step == 2:
                self.scores = data['scores']
                self.info['reach'] += 1
        if tag == 'DORA':
            self.dora_indicator.append(int(data['hai']))
        if tag == 'BYE':
            player = data['index']
            self.player_online[player] = False
        if tag == 'RESUME':
            player = data['index']
            self.player_online[player] = True

    def add(self, dict_in):
        tag, data = dict_in['tag'], dict_in['data']
        if tag == 'INIT':
            self.parse_init(data)
        elif tag in ['AGARI', 'RYUUKYOKU']:
            self.result = {'result': tag, 'data': data}
        else:
            self.parse_action(tag, data)


for round in mjdata_dict['rounds']:
    roundsim = RoundSimulator(player_rate=player_rate)
    for data in round:
        roundsim.add(data)
    kyokumen_list = copy.deepcopy(roundsim.kyokumen_list)
    print(kyokumen_list)
    print(roundsim.result)
    exit()


