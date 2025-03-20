# app.py (modifié)
from flask import Flask, request, jsonify
from flask_cors import CORS
import numpy as np
from random import randint, choice

app = Flask(__name__)
CORS(app)

class Patient:
    def __init__(self, id, esi_level, needs):
        self.id = id
        self.esi_level = esi_level
        self.needs = needs

class CHU:
    def __init__(self, id, resources, distance):
        self.id = id
        self.resources = resources.copy()
        self.assigned_patients = {}
        self.available_resources = resources.copy()
        self.distance = distance  # Nouvelle propriété pour la distance

def update_resources(chu, patient, action="remove"):
    for r, qty in patient.needs.items():
        if action == "remove":
            chu.available_resources[r] = chu.available_resources.get(r, 0) - qty
            print(f"CHU {chu.id} - {r} décrémenté: {chu.available_resources[r]}")
        elif action == "add":
            chu.available_resources[r] = chu.available_resources.get(r, 0) + qty
            print(f"CHU {chu.id} - {r} incrémenté: {chu.available_resources[r]}")

def has_sufficient_resources(chu, needs):
    for r, qty in needs.items():
        available = chu.available_resources.get(r, 0)
        if available < qty:
            print(f"Échec pour {r}: besoin {qty}, disponible {available} dans CHU {chu.id}")
            return False
    print(f"Ressources suffisantes dans CHU {chu.id}")
    return True

def assign_to_chu(chu, patient):
    chu.assigned_patients[patient.id] = patient
    update_resources(chu, patient, "remove")

def release_from_chu(chu, patient_id):
    if patient_id in chu.assigned_patients:
        patient = chu.assigned_patients[patient_id]
        update_resources(chu, patient, "add")
        del chu.assigned_patients[patient_id]

def generate_random_resources(nb_chus):
    chus = []
    for i in range(nb_chus):
        resources = {
            "lit": randint(35, 45),
            "specialiste": randint(15, 25),
            "generaliste": randint(15, 25),
            "defibrillateur": randint(3, 8),
            "scanner": randint(2, 5),
            "respirateur": randint(5, 10),
            "poche_sang": randint(50, 100)
        }
        # Générer une distance fictive entre 1 et 50 km
        distance = randint(1, 50)
        chus.append(CHU(i, resources, distance))
    return chus

def generate_patient_needs(esi_level, requested_resources):
    needs = {}
    if esi_level == 1:
        needs = {"lit": 1, "specialiste": 1, "defibrillateur": randint(0, 1), "respirateur": randint(0, 1), "poche_sang": randint(0, 3)}
    elif esi_level == 2:
        needs = {"lit": 1, "specialiste": 1, "scanner": randint(0, 1), "respirateur": randint(0, 1)}
    elif esi_level == 3:
        needs = {"lit": 1, "scanner": randint(0, 1), "specialiste": randint(0, 1), "generaliste": randint(0, 1)}
    elif esi_level == 4:
        needs = {"lit": randint(0, 1), "scanner": randint(0, 1), "generaliste": randint(0, 1)}
    elif esi_level == 5:
        needs = {"lit": randint(0, 1)} if randint(0, 1) else {}
    
    resource_mapping = {
        "Lit": "lit",
        "Respirateur": "respirateur",
        "Oxygène": "poche_sang",
        "Sang": "poche_sang",
        "Spécialiste": "specialiste",
        "Généraliste": "generaliste",
        "Défibrillateur": "defibrillateur"
    }
    for res in requested_resources:
        key = resource_mapping.get(res)
        if key:
            needs[key] = needs.get(key, 0) + 1
        else:
            print(f"Ressource non reconnue: {res}")

    print(f"Besoins générés pour ESI {esi_level}: {needs}")
    return needs

def assign_patients_with_reallocation(patients, chus):
    allocation = {p.id: chu.id for chu in chus for p in chu.assigned_patients.values()}
    reallocations = []

    patients_sorted = sorted(patients, key=lambda p: p.esi_level)
    for patient in patients_sorted:
        # Trouver tous les CHU avec assez de ressources
        eligible_chus = [chu for chu in chus if has_sufficient_resources(chu, patient.needs)]
        
        if eligible_chus:
            # Choisir le CHU le plus proche parmi ceux qui ont assez de ressources
            best_chu = min(eligible_chus, key=lambda chu: chu.distance)
            print(f"CHU {best_chu.id} sélectionné pour patient {patient.id} (distance: {best_chu.distance} km)")
            allocation[patient.id] = best_chu.id
            assign_to_chu(best_chu, patient)
        else:
            # Si aucun CHU n'a assez de ressources et ESI <= 3, tenter une réallocation
            if patient.esi_level <= 3:
                for chu in chus:
                    to_release = [p for p in chu.assigned_patients.values() if p.esi_level > patient.esi_level]
                    if to_release:
                        candidate = max(to_release, key=lambda p: p.esi_level)
                        release_from_chu(chu, candidate.id)
                        reallocations.append((candidate.id, chu.id, patient.id, candidate.needs))
                        if has_sufficient_resources(chu, patient.needs):
                            allocation[patient.id] = chu.id
                            assign_to_chu(chu, patient)
                            break

    unassigned = [p for p in patients if p.id not in allocation]
    return allocation, reallocations, unassigned

# Initialiser 10 CHU au lieu de 3
chus = generate_random_resources(10)

@app.route('/assign_patient', methods=['POST'])
def assign_patient():
    data = request.json
    patient_id = data.get('id', f"PAT-{randint(1000, 9999)}")
    esi_level = int(data['esi'])
    requested_resources = data.get('ressources', [])

    print(f"Données reçues: id={patient_id}, esi={esi_level}, ressources={requested_resources}")

    patient_needs = generate_patient_needs(esi_level, requested_resources)
    patient = Patient(patient_id, esi_level, patient_needs)

    allocation, reallocations, unassigned = assign_patients_with_reallocation([patient], chus)

    response = {
        "patient_id": patient_id,
        "assigned_chu": allocation.get(patient_id, None),
        "chus": [
            {
                "id": chu.id,
                "available_resources": chu.available_resources,
                "assigned_patients": len(chu.assigned_patients),
                "distance": chu.distance  # Ajouter la distance dans la réponse
            }
            for chu in chus
        ],
        "reallocations": reallocations,
        "unassigned": [p.id for p in unassigned]
    }
    return jsonify(response)

if __name__ == "__main__":
    app.run(debug=True, port=5000)