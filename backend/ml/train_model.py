import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
import joblib
import os

def generate_synthetic_data(num_samples=5000):
    """
    Genera un dataset sintético simulando partidos internacionales.
    Features:
      - form_diff: Diferencia de forma (0 a 10) entre equipo A y B.
      - goal_diff_avg: Diferencia promedio de goles a favor vs en contra.
      - h2h_dominance: % de victorias históricas del equipo A sobre el B.
    Target:
      - result: 1 (Gana A), 0 (No Gana A)
    """
    np.random.seed(42)
    
    # Random features
    form_diff = np.random.uniform(-5.0, 5.0, num_samples) 
    goal_diff_avg = np.random.uniform(-2.0, 2.0, num_samples)
    h2h_dominance = np.random.uniform(0.0, 1.0, num_samples)
    
    # Formula to simulate probability of Team A winning
    # Base 50% chance, adjusted by form, goals, and history
    logit = (form_diff * 0.4) + (goal_diff_avg * 1.5) + ((h2h_dominance - 0.5) * 2.0)
    prob_a_wins = 1 / (1 + np.exp(-logit)) # Sigmoid
    
    # Introduce some noise/randomness
    random_factor = np.random.uniform(0, 1, num_samples)
    result = (prob_a_wins > random_factor).astype(int)
    
    df = pd.DataFrame({
        'form_diff': form_diff,
        'goal_diff_avg': goal_diff_avg,
        'h2h_dominance': h2h_dominance,
        'result': result
    })
    
    return df

def train_and_save_model():
    print("Generando dataset histórico (simulado)...")
    df = generate_synthetic_data(10000)
    
    X = df[['form_diff', 'goal_diff_avg', 'h2h_dominance']]
    y = df['result']
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    print("Entrenando RandomForestClassifier...")
    model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
    model.fit(X_train, y_train)
    
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    
    print(f"Modelo Entrenado. Accuracy en Test: {accuracy:.2f}")
    print("\nReporte de Clasificación:")
    print(classification_report(y_test, y_pred))
    
    # Save model
    model_path = os.path.join(os.path.dirname(__file__), 'model.pkl')
    joblib.dump(model, model_path)
    print(f"Modelo guardado exitosamente en: {model_path}")

if __name__ == "__main__":
    train_and_save_model()
