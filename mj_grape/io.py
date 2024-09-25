#! /usr/bin/env python

from tenhou_log_utils.io import load_mjlog
from tenhou_log_utils.parser import parse_mjlog
import numpy as np
import copy

MAX_PAI_NUMBER = 136

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
        self.tile_last_discarded = -1
        return
    
    def parse_init(self, data):
        self.leader[int(data['oya'])] = True
        self.scores = data['scores']
        self.hands = data['hands']
        self.melds = [[], [], [], []]
        self.melds_indicator = [[], [], [], []]
        self.info = {
            'round': int(data['round']),
            'combo' : int(data['combo']),
            'reach': int(data['reach']),
            }
        self.dora_indicator.append(int(data['dora']))
        self.pai_open[self.dora_indicator] = True

    def update_datalist(self, player, discard_pai, is_tsumo_giri, is_skip=False):
        kyokumen = {
            'player': player,
            'discard': discard_pai,
            'is_tsumo_giri': is_tsumo_giri,
            'is_skip': is_skip,
            'riich_state': self.player_reach_step[player],
            'hands': copy.deepcopy(self.hands[player]),
            'melds': copy.deepcopy(self.melds[player]),
            'melds_indicator': copy.deepcopy(self.melds_indicator[player]),
            'online': self.player_online[player],
            'oya': self.leader[player],
            'dora_indicator': list(self.dora_indicator),
            'score': self.scores[player],
            'info': copy.deepcopy(self.info),
        }
        self.kyokumen_list.append(kyokumen)

    def parse_action(self, tag, data):
        if tag == 'DISCARD':
            player = int(data['player'])
            tile = int(data['tile'])
            num_skip = 0 if self.player_last_discard == -1 else (player - self.player_last_discard) % 4 - 1 
            for i in range(num_skip):
                ip = player - num_skip + i
                ip = 3 if ip == -1 else ip
                self.update_datalist(ip, MAX_PAI_NUMBER, False, is_skip=True)
            is_tsumo_giri = (self.player_last_draw == player) and (self.hands[player][-1] == tile)
            self.hands[player] = [i for i in self.hands[player] if i != tile]
            self.update_datalist(player, tile, is_tsumo_giri)
            self.player_last_discard = player
            self.tile_last_discarded = tile
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
                melds_indicator = [0, 0, 0, 0]
            elif call_type == 'KaKan':
                non_Kan = [(m,z) for (m,z) in zip(self.melds[caller],self.melds_indicator[caller]) if not set(m) <= set(mentsu)]
                old_mentsu, old_indicator = [(m,z) for (m,z) in zip(self.melds[caller],self.melds_indicator[caller]) if set(m) <= set(mentsu)][0]
                old_gotten = int(np.array(old_mentsu)[np.array(old_indicator, dtype=bool)][0])
                new_gotten = list((set(mentsu) - set(old_mentsu)))[0]
                melds_indicator = ((np.array(mentsu) == old_gotten)*1 + (np.array(mentsu) == new_gotten)*2).astype(int).tolist()
                if len(non_Kan) == 0:
                    self.melds[caller], self.melds_indicator[caller] = [], []
                else:
                    self.melds[caller], self.melds_indicator[caller] = [list(a) for a in zip(*non_Kan)]
            else:
                melds_indicator = (np.array(mentsu) == self.tile_last_discarded).astype(int).tolist()
            self.melds[caller].append(mentsu)
            self.melds_indicator[caller].append(melds_indicator)
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

    def read_round(self, round):
        for data in round:
            self.add(data)
        kyokumen_list = copy.deepcopy(self.kyokumen_list)
        return kyokumen_list, self.result


def mjlog_to_round_data(mjlog_file):
    mjdata_dict = parse_mjlog(load_mjlog(mjlog_file))
    meta_data = mjdata_dict['meta']
    player_rate = [float(player['rate']) for player in meta_data['UN']]
    rule_set = meta_data['GO']['config']
    data_list = []
    for round in mjdata_dict['rounds']:
        roundsim = RoundSimulator(player_rate=player_rate)
        kyokumen_list, result = roundsim.read_round(round)
        data_list.append({
            'rule_set': rule_set,
            'action_list': kyokumen_list,
            'result': result
        })
    return data_list