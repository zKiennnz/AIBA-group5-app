import pandas as pd
import numpy as np
from xgboost import XGBRegressor
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.preprocessing import StandardScaler
from sklearn.neural_network import MLPRegressor
from sklearn.ensemble import StackingRegressor
from scipy import stats

# Đọc dữ liệu
df = pd.read_csv('cityu10d_train_dataset (1).csv')

# Loại bỏ các biến không liên quan (ID, ApplicationDate)
df_cleaned = df.drop(columns=['ID', 'ApplicationDate'])

# Tách các biến độc lập (X) và biến phụ thuộc (y)
X = df_cleaned.drop(columns=['RiskScore'])
y = df_cleaned['RiskScore']

# Xử lý dữ liệu phân loại
categorical_cols = X.select_dtypes(include=['object']).columns
for col in categorical_cols:
    X[col] = X[col].astype(str)

# Mã hóa các biến phân loại
X_encoded = pd.get_dummies(X, drop_first=True)

# Lọc các biến có ý nghĩa thống kê dựa trên p-value (p-value < 0.05)
significant_columns = []
for col in X_encoded.columns:
    corr, p_value = stats.pearsonr(X_encoded[col], y)
    if p_value < 0.05:
        significant_columns.append(col)

# Chỉ giữ lại các biến có ý nghĩa thống kê
X_significant = X_encoded[significant_columns]

# Chuẩn hóa dữ liệu với StandardScaler
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X_significant)

# Tách dữ liệu thành tập huấn luyện và kiểm tra
X_train, X_test, y_train, y_test = train_test_split(X_scaled, y, test_size=0.2, random_state=42)

# Base learners
xgb = XGBRegressor(n_estimators=2500, learning_rate=0.005, max_depth=6, subsample=0.8, colsample_bytree=0.8, random_state=42)
rf = RandomForestRegressor(n_estimators=300, max_depth=10, random_state=42)
gbr = GradientBoostingRegressor(n_estimators=200, learning_rate=0.05, max_depth=5, random_state=42)

# Meta-learner
mlp = MLPRegressor(hidden_layer_sizes=(64, 32), activation='relu', solver='adam', random_state=42, max_iter=500, alpha=0.005)

# Stacking Regressor
stacking_regressor = StackingRegressor(
    estimators=[('xgb', xgb), ('rf', rf), ('gbr', gbr)],
    final_estimator=mlp,
    passthrough=True  # Sử dụng cả đặc trưng gốc và dự đoán base learners
)

# Áp dụng Cross-validation để đánh giá mô hình
cv_scores = cross_val_score(stacking_regressor, X_scaled, y, cv=5, scoring='neg_mean_absolute_error', n_jobs=-1)

# In kết quả của Cross-validation
print(f"Cross-validation MAE: {-cv_scores.mean()}")

# Huấn luyện Stacking Regressor
stacking_regressor.fit(X_train, y_train)

# Dự đoán
y_pred = stacking_regressor.predict(X_test)

# Đánh giá hiệu suất
mae = mean_absolute_error(y_test, y_pred)
r_squared = r2_score(y_test, y_pred)

# In kết quả
print(f"Stacking with MLP - Mean Absolute Error (MAE): {mae}")
print(f"Stacking with MLP - R-squared: {r_squared}")

import pickle
# Save the pipeline to a pickle file
with open('decision_tree_pipeline.pkl', 'wb') as file:
    stacking_regressor.fit(X_train, y_train)

print("Stacking trained and saved to stacking_deploy.pkl")

%%writefile app.py

import streamlit as st
import pandas as pd
import pickle
from pyngrok import ngrok

# Load the pipeline from the pickle file
with open('stacking_deploy.pkl', 'rb') as file:
    loaded_pipeline = pickle.load(file)

# Set up the Streamlit app title
st.title("Loan Approval Prediction App")

# Create input fields for user to enter data
age = st.number_input("Age", min_value=18, max_value=100, value=30)
annual_income = st.number_input("Annual Income", min_value=0, value=50000)
credit_score = st.number_input("Credit Score", min_value=300, max_value=850, value=650)
employment_status = st.selectbox("Employment Status", ["Employed", "Unemployed", "Self-Employed"])
education_level = st.selectbox("Education Level", ["Bachelor", "Master", "PhD"])
loan_amount = st.number_input("Loan Amount", min_value=0, value=10000)
loan_duration = st.number_input("Loan Duration (months)", min_value=1, value=12)

# Create a button to trigger prediction
if st.button("Predict"):
    # Create a DataFrame from user input
    new_data = pd.DataFrame({
        'Age': [age],
        'AnnualIncome': [annual_income],
        'CreditScore': [credit_score],
        'EmploymentStatus': [employment_status],
        'EducationLevel': [education_level],
        'LoanAmount': [loan_amount],
        'LoanDuration': [loan_duration]
    })

    # Make prediction using the loaded pipeline
    prediction = loaded_pipeline.predict(new_data)

    # Display the prediction
    if prediction[0] == 1:
        st.success("Loan Approved!")
    else:
        st.error("Loan Rejected.")
