import pandas as pd
import time
from datetime import datetime
from corona import logger
from corona.utils import retry, timer


min_duration = 150
#### group rssi measurments bewteen two devices into contacts
@retry(Exception)
def get_observed_contacts(db, device,start_date,end_date,grouping_th):
    contacts = {}
    cursor = db.cursor()
    with timer("db query getBluetoothPairing"):
        cursor.execute("""select * from  getBluetoothPairing(?,?,?) order by pairedtime""",device,start_date,end_date)
    row = cursor.fetchone()
    while row:
        pair = row.paireddeviceid if device != row.paireddeviceid else row.uuid
        rssi = row.rssi
        ts_hr = row.pairedtime
        ts_unix = row.pairedtime_ut
        if device in contacts:
            if  pair in contacts[device]:
                num_contacts = len(contacts[device][pair])
                last_ts_unix = contacts[device][pair][num_contacts]['last_ts_unix']
                if ts_unix-last_ts_unix <= grouping_th:
                    contacts[device][pair][num_contacts]['last_ts_unix'] = ts_unix
                    contacts[device][pair][num_contacts]['last_ts_hr'] = ts_hr
                    contacts[device][pair][num_contacts]['rssi'].append(rssi)
                    contacts[device][pair][num_contacts]['platform']=row.pair_platform
                else:
                    contacts[device][pair][num_contacts+1]={}
                    contacts[device][pair][num_contacts+1]['rssi'] = []
                    contacts[device][pair][num_contacts+1]['start_ts_unix'] = ts_unix
                    contacts[device][pair][num_contacts+1]['last_ts_unix'] = ts_unix
                    contacts[device][pair][num_contacts+1]['last_ts_hr'] = ts_hr
                    contacts[device][pair][num_contacts+1]['start_ts_hr'] = ts_hr
                    contacts[device][pair][num_contacts+1]['rssi'].append(rssi)
                    contacts[device][pair][num_contacts+1]['platform']=row.pair_platform
            else:
                contacts[device][pair]={}
                contacts[device][pair][1]={}
                contacts[device][pair][1]['rssi'] = []
                contacts[device][pair][1]['start_ts_unix'] = ts_unix
                contacts[device][pair][1]['last_ts_unix'] = ts_unix
                contacts[device][pair][1]['last_ts_hr'] = ts_hr
                contacts[device][pair][1]['start_ts_hr'] = ts_hr
                contacts[device][pair][1]['rssi'].append(rssi)
                contacts[device][pair][1]['platform']=row.pair_platform
        else:
             contacts[device]={}
             contacts[device][pair]={}
             contacts[device][pair][1]={}
             contacts[device][pair][1]['rssi'] = []
             contacts[device][pair][1]['start_ts_unix'] = ts_unix
             contacts[device][pair][1]['last_ts_unix'] = ts_unix
             contacts[device][pair][1]['last_ts_hr'] = ts_hr
             contacts[device][pair][1]['start_ts_hr'] = ts_hr
             contacts[device][pair][1]['rssi'].append(rssi)
             contacts[device][pair][1]['platform']=row.pair_platform
        row = cursor.fetchone()
    cursor.close()
    return contacts


### use the measured rssi values to detemrine whether a contact is very close, close or far
def desc_contacts(contacts,ios_vc,ios_c,ios_f,android_vc,android_c,android_f):
    data = []
    for device in contacts.keys():
        for pair in contacts[device].keys():
            for contact in contacts[device][pair].keys():
                platform = contacts[device][pair][contact]['platform']
                if platform not in ['ios','android']:
                    continue
                start_ts_unix = contacts[device][pair][contact]['start_ts_unix']
                end_ts_unix = contacts[device][pair][contact]['last_ts_unix']
                duration = end_ts_unix - start_ts_unix
                total_length = len(contacts[device][pair][contact]['rssi'])
                vc_length = 0
                c_length = 0
                vc_list = []
                c_list = []
                f_list =  []
                if duration < min_duration:
                    duration = min_duration
                    end_ts_unix = start_ts_unix + min_duration
                if platform == 'ios':
                    vc_list = [i for i in contacts[device][pair][contact]['rssi'] if ios_vc<=i]
                    c_list = [i for i in contacts[device][pair][contact]['rssi'] if ios_c<=i]
                    f_list = [i for i in contacts[device][pair][contact]['rssi'] if ios_f<=i]
                if platform == 'android':
                    vc_list = [i for i in contacts[device][pair][contact]['rssi'] if android_vc<=i]
                    c_list = [i for i in contacts[device][pair][contact]['rssi'] if android_c<=i]
                    f_list = [i for i in contacts[device][pair][contact]['rssi'] if android_f<=i]
                vc_length = len(vc_list)
                c_length = len(c_list)-vc_length
                f_length = len(f_list)-c_length - vc_length
                contact = [device,pair,datetime.utcfromtimestamp(start_ts_unix).strftime('%Y-%m-%d %H:%M:%S'),datetime.utcfromtimestamp(end_ts_unix).strftime('%Y-%m-%d %H:%M:%S'),start_ts_unix,end_ts_unix,duration,total_length,vc_length,c_length,f_length]
                data.append(contact)
                data.append(contact)
    contact_stats = pd.DataFrame(data,columns = ['device','pair','start_ts_hr','end_ts_hr','start_ts_unix','end_ts_unix','duration','total_length','vc_length','c_length','f_length'])
    return contact_stats

### use measurments from other nearby devices to discover hidden devices - this is important to overcome the ios limitation
def find_hidden_devices(device,contact_stats,db,start_date,end_date,grouping_th,ios_vc,ios_c,ios_f,android_vc,android_c,android_f):
    very_close_contact = contact_stats[contact_stats.vc_length>0]
    overlap_hidden = []
    visited = {}
    for index, row in very_close_contact.iterrows():
        peer_device = row["pair"]
        if peer_device in visited.keys():
            continue
        visited[peer_device] = 1
        raw_contacts = get_observed_contacts(db, peer_device,start_date,end_date,grouping_th)
        peer_contacts = desc_contacts(raw_contacts,ios_vc,ios_c,ios_f,android_vc,android_c,android_f)
        for cont in range(len(peer_contacts)):
            if  peer_contacts.loc[cont,"vc_length"]>0:
                if peer_contacts.loc[cont,"device"] == device or peer_contacts.loc[cont,"pair"] == device:
                    continue
                curr_device = peer_contacts.loc[cont,"device"] if peer_contacts.loc[cont,"device"] != peer_device else peer_contacts.loc[cont,"pair"]
                start_curr = peer_contacts.loc[cont,"start_ts_unix"]
                end_curr = peer_contacts.loc[cont,"end_ts_unix"]
                start_curr_hr = peer_contacts.loc[cont,"start_ts_hr"]
                end_curr_hr = peer_contacts.loc[cont,"end_ts_hr"]

                very_close_peer = very_close_contact[very_close_contact.pair == peer_device]
                for index2,row2 in very_close_peer.iterrows():
                    start = row2["start_ts_unix"]
                    end = row2["end_ts_unix"]
                    if start_curr < end and start<end_curr:
                        duration_curr = end_curr - start_curr
                        if duration_curr < min_duration:
                            duration_curr = min_duration
                        start_intersect = max(start,start_curr)
                        end_intersect = min(end,end_curr)
                        duration = end_intersect - start_intersect
                        if  duration < min_duration:
                            duration = min_duration
                            end_intersect = end_intersect + min_duration
                        length_curr = peer_contacts.loc[cont,"total_length"]
                        vc_length_curr = peer_contacts.loc[cont,"vc_length"]
                        length = (duration/duration_curr)*int(length_curr)
                        c_length = (duration/duration_curr)*int(vc_length_curr)
                        contact = [device,curr_device,datetime.utcfromtimestamp(start_intersect).strftime('%Y-%m-%d %H:%M:%S'),datetime.utcfromtimestamp(end_intersect).strftime('%Y-%m-%d %H:%M:%S'),start_intersect,end_intersect,duration,length,0,c_length,0]
                        overlap_hidden.append(contact)

    ## remember check close duration
    hidden_devices = pd.DataFrame(overlap_hidden,columns =['device','pair','start_ts_hr','end_ts_hr','start_ts_unix','end_ts_unix','duration','total_length','vc_length','c_length','f_length'])
    return hidden_devices

## combine original contacts and hidden contacts
def combine_contacts(contact_stats,hidden_devices):
    all_evts = []
    ## for each direct contact check if there is an overlapping hidden contact
    for evt in range(len(contact_stats)):
        pair = contact_stats.loc[evt,"pair"]
        start = contact_stats.loc[evt,"start_ts_unix"]
        end =   contact_stats.loc[evt,"end_ts_unix"]
        length = contact_stats.loc[evt,"total_length"]
        vc =    contact_stats.loc[evt,"vc_length"]
        c = contact_stats.loc[evt,"c_length"]
        f = contact_stats.loc[evt,"f_length"]
        c_hidden = 0
        length_hidden = 0
        for hidden_evt in range(len(hidden_devices)):
            if hidden_devices.loc[hidden_evt,"pair"] == pair:
                start_curr = hidden_devices.loc[hidden_evt,"start_ts_unix"]
                end_curr =   hidden_devices.loc[hidden_evt,"end_ts_unix"]
                if start < end_curr and start_curr < end:
                    start = min(start,start_curr)
                    end = max(end,end_curr)
                    length_hidden = hidden_devices.loc[hidden_evt,"total_length"]
                    c_hidden = hidden_devices.loc[hidden_evt,"c_length"]
        duration = end -start
        if duration < min_duration :
            duration = min_duration
        contact = [contact_stats.loc[evt,"device"],pair,datetime.utcfromtimestamp(start).strftime('%Y-%m-%d %H:%M:%S'), datetime.utcfromtimestamp(end).strftime('%Y-%m-%d %H:%M:%S'), start, end, duration,length,length_hidden,vc,c,c_hidden,f]
        all_evts.append(contact)
    visited = {}
    grouped_evts = []
    combined_evts = []
    ## combine contacts that have same starting and ending times
    for i in range(len(all_evts)):
        if i in visited.keys():
            continue
        evt_i = all_evts[i]
        device_i = evt_i[0]
        pair_i = evt_i[1]
        start_hr_i = evt_i[2]
        end_hr_i = evt_i[3]
        start_ts_i = evt_i[4]
        end_ts_i = evt_i[5]
        dur_i = evt_i[6]
        length_i = evt_i[7]
        length_hidden_i = evt_i[8]
        vc_i = evt_i[9]
        c_i = evt_i[10]
        c_hidden_i = evt_i[11]
        f_i = evt_i[12]
        for j in range (i+1,len(all_evts)):
            evt_j = all_evts[j]
            pair_j = evt_j[1]
            start_ts_j = evt_j[4]
            end_ts_j = evt_j[5]
            if pair_i == pair_j and start_ts_i==start_ts_j and end_ts_i==end_ts_j:
                visited[j] = 1
                length_i = length_i + evt_j[7]
                vc_i = vc_i + evt_j[9]
                c_i = c_i + evt_j[10]
                f_i = f_i + evt_j[12]
        length = length_i+length_hidden_i
        c_length = c_i+c_hidden_i
        contact = [device_i,pair_i,start_hr_i,end_hr_i,start_ts_i,end_ts_i,dur_i,length,vc_i,c_length,f_i]
        combined_evts.append(contact)
    ## now checking partially overlapping encounters
    visited = {}
    for i in range(len(combined_evts)):
        if i in visited.keys():
            continue
        evt_i = combined_evts[i]
        device_i = evt_i[0]
        pair_i = evt_i[1]
        start_ts_i = evt_i[4]
        end_ts_i = evt_i[5]
        dur_i = evt_i[6]
        length_i = evt_i[7]
        vc_i = evt_i[8]
        c_i = evt_i[9]
        f_i = evt_i[10]
        for j in range(i+1,len(combined_evts)):
            evt_j = combined_evts[j]
            pair_j = evt_j[1]
            start_ts_j = evt_j[4]
            end_ts_j = evt_j[5]
            if pair_i == pair_j and start_ts_i<end_ts_j and start_ts_j<end_ts_i:
                visited[j] = 1
                start_ts_i = min(start_ts_i,start_ts_j)
                end_ts_i = max(end_ts_i,end_ts_j)
                dur_i = end_ts_i - start_ts_i
                ## we choose the number of measurements in the longest stretsh -- this needs to be discussed
                length_i = max(length_i,evt_j[7])
                vc_i = max(vc_i,evt_j[8])
                c_i = max(c_i,evt_j[9])
                f_i = max(f_i,evt_j[10])
        contact = [device_i,pair_i,datetime.utcfromtimestamp(start_ts_i).strftime('%Y-%m-%d %H:%M:%S'),datetime.utcfromtimestamp(end_ts_i).strftime('%Y-%m-%d %H:%M:%S'),start_ts_i,end_ts_i,dur_i,length_i,vc_i,c_i,f_i]
        grouped_evts.append(contact)
    grouped_contacts = pd.DataFrame(grouped_evts,columns =['device','pair','start_ts_hr','end_ts_hr','start_ts_unix','end_ts_unix','duration','total_length','vc_length','c_length','f_length'])
    ## here we check seconadry contacts that do not overlap with primary contacts or with primary contact peers
    remaining_contacts = []
    for hidden_evt in range(len(hidden_devices)):
        pair = hidden_devices.loc[hidden_evt,"pair"]
        start = hidden_devices.loc[hidden_evt,"start_ts_unix"]
        end =   hidden_devices.loc[hidden_evt,"end_ts_unix"]
        length = hidden_devices.loc[hidden_evt,"total_length"]
        vc = hidden_devices.loc[hidden_evt,"vc_length"]
        c = hidden_devices.loc[hidden_evt,"c_length"]
        f = hidden_devices.loc[hidden_evt,"f_length"]
        flag = 0
        for evt in range(len(grouped_contacts)):
            if grouped_contacts.loc[evt,"pair"] == pair:
                start_curr = grouped_contacts.loc[evt,"start_ts_unix"]
                end_curr =   grouped_contacts.loc[evt,"end_ts_unix"]
                if start < end_curr and start_curr < end:
                    flag = 1
                    continue
        if not flag:
            duration = end -start
            if(duration < min_duration):
                duration = min_duration
                end = start + min_duration
            contact = [grouped_contacts.loc[evt,"device"],pair,datetime.utcfromtimestamp(start).strftime('%Y-%m-%d %H:%M:%S'),datetime.utcfromtimestamp(end).strftime('%Y-%m-%d %H:%M:%S'),start,end,(end-start),length,vc,c,f]
            remaining_contacts.append(contact)
## here we filter secondary contacts that are reported by several nearby phones
    visited = {}
    for i in range(len(remaining_contacts)):
        if i in visited.keys():
            continue
        evt_i = remaining_contacts[i]
        device_i = evt_i[0]
        pair_i = evt_i[1]
        start_ts_i = evt_i[4]
        end_ts_i = evt_i[5]
        dur_i = evt_i[6]
        length_i = evt_i[7]
        vc_i = evt_i[8]
        c_i = evt_i[9]
        f_i = evt_i[10]
        for j in range(i+1,len(remaining_contacts)):
            evt_j = remaining_contacts[j]
            pair_j = evt_j[1]
            start_ts_j = evt_j[4]
            end_ts_j = evt_j[5]
            if pair_i == pair_j and start_ts_i<end_ts_j and start_ts_j<end_ts_i:
                visited[j] = 1
                start_ts_i = min(start_ts_i,start_ts_j)
                end_ts_i = max(end_ts_i,end_ts_j)
                length_i = max(length_i,evt_j[6])
                vc_i = max(vc_i,evt_j[8])
                c_i = max(c_i,evt_j[9])
                f_i = max(f_i,evt_j[10])
        contact = [device_i,pair_i,datetime.utcfromtimestamp(start_ts_i).strftime('%Y-%m-%d %H:%M:%S'),datetime.utcfromtimestamp(end_ts_i).strftime('%Y-%m-%d %H:%M:%S'),start_ts_i,end_ts_i,(end_ts_i-start_ts_i),length_i,vc_i,c_i,f_i]
        grouped_evts.append(contact)
    # calssifying contacts
    classified_contacts = []
    for i in range(len(grouped_evts)):
        contact_i = grouped_evts[i]
        duration = contact_i[6]
        length_i = contact_i[7]
        vc_i = contact_i[8]
        c_i = contact_i[9]
        f_i = contact_i[10]
        duration_close = duration*(vc_i+c_i)/length_i
        indicator = 0
        if length_i<2*vc_i:
            vc_i = duration
            c_i = 0
            f_i = 0
            indicator = 1
        else:
            if length_i<2*(vc_i+c_i):
                vc_i = 0
                c_i = duration
                f_i = 0
                indicator = 1
            else:
                if duration_close >= 900:
                    vc_i = 0
                    c_i = duration
                    f_i = 0
                    indicator = 1
                else:
                    if length_i < 2*f_i:
                        vc_i = 0
                        c_i = 0
                        f_i = duration
                        indicator = 1
                    else:
                        if 0<vc_i or 0<c_i:
                            vc_i = 0
                            c_i = 0
                            f_i = 0
                            indicator = 1
                        else:
                            vc_i = 0
                            c_i = 0
                            f_i = 0
                            indicator = 0
        current_contact = [contact_i[0],contact_i[1],contact_i[2],contact_i[3],contact_i[4],contact_i[5],contact_i[6],length_i,vc_i,c_i,f_i,indicator]
        classified_contacts.append(current_contact)
    all_contacts = pd.DataFrame(classified_contacts,columns =['device','pair','start_ts_hr','end_ts_hr','start_ts_unix','end_ts_unix','duration','total_length','vc_length','c_length','f_length','is_close'])

    return all_contacts

def get_contacts(device,start_date,end_date, db, grouping_th=300,ios_vc=-55,ios_c=-65,ios_f=-75,android_vc=-65,android_c=-75,android_f=-85):
    initial_contacts = get_observed_contacts(db,device,start_date,end_date,grouping_th)
    annotated_contacts = desc_contacts(initial_contacts,ios_vc,ios_c,ios_f,android_vc,android_c,android_f)
    hidden_contacts = find_hidden_devices(device,annotated_contacts,db,start_date,end_date,grouping_th,ios_vc,ios_c,ios_f,android_vc,android_c,android_f)
    contacts = combine_contacts(annotated_contacts,hidden_contacts)
    return contacts

def convert_frame(df):
    """ Converts output of get_contacts to pandas frame with columns
    ["uuid", "paireddeviceid", "encounterstarttime", "duration", "very_close_duration","close_duration"]
    """
    df = df.drop(columns=[ "start_ts_hr", "end_ts_hr", "end_ts_unix", "total_length" ])
    df.rename(columns = {'device' : 'uuid', 'pair' : 'paireddeviceid',
                         'start_ts_unix' : 'encounterstarttime',
                         'vc_length' : 'very_close_duration',
              'c_length' : 'close_duration', 'f_length':'relatively_close_duration' , 'is_close':'within_two_meters'}, inplace = True)
    return df
