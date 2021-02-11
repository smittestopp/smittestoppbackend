import random
import hashlib
from string import ascii_letters
from corona import logger


def contacts_to_dicts(uuid, contacts, device_info, add_random_salt=False):
    """ Creates a list of dictionaries to anonymously 
    log all detected contacts (not aggregated as a contact list) 
    :params uuid: Patient uuid (string)
    :params contacts: contacts argument of a ContactGraphResult object 
    :params device_info: dict of uuid -> List of device info tuples
    :params add_random_salt: If true adds a random combination of letters infront of uuids before 
                             hashing, where combination changes on each call of function.
    """
    
    salt = ''
    all_contacts = []
    if add_random_salt:
        aux_letters = list(ascii_letters)
        random.shuffle(aux_letters)
        salt= ''.join(aux_letters)
    hash_patient = hashlib.sha512((salt+':'+uuid).encode('utf-8')).hexdigest()
    for (uuid1, uuid2), contact_list in contacts.items():
        for contact in contact_list:
            hash_susceptible = hashlib.sha512((salt+':'+uuid2).encode('utf-8')).hexdigest()
            all_contacts.append({
                'event' : 'contact_logger',
                'case' : hash_patient,
                'case_device': device_info[uuid],  # Is it that uuid == uuid1
                'contact' : hash_susceptible,
                'contact_device': device_info[uuid2],
                'start_time' : contact.time_from(),
                'end_time' : contact.time_to(),
                'location' : contact.pois(),
                'duration' : contact.duration(),
                'contact_type' : contact.contact_type(),
                'median_distance' : contact.median_distance(),
                'risk_score' : contact.risk_score(),
                'risk_category' : contact.risk_category(), # Store risk_category of contact_list or compute individually?
                'FHI_valid' : contact_list.include_in_report(),
            })
    return all_contacts


def log_contacts(uuid, contacts, device_info, add_random_salt=False):
    """ Writes a list [contact1_dict, contact2_dict,...] into the given txt file
    where each row corresponds to one case.
    :params uuid: Patient uuid (string)
    :params contacts: contacts argument of a ContactGraphResult object 
    :params device_info: dict of uuid -> List of device info tuples
    :params logfile: File to log the contacts 
    :params mode: if 'a' contacts are appended to logfile, if 'w' previous content is overwritten overwritten
    :params add_random_salt: If true adds a random combination of letters infront of uuids before 
                             hashing, where combination changes on each call of function.
    
    """
    contacts_list = contacts_to_dicts(uuid, contacts, add_random_salt=add_random_salt, device_info=device_info)
    for contact in contacts_list:
        logger.info(contact)





