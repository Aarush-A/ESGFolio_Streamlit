import streamlit as st
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os
from PIL import Image

# Set page config
st.set_page_config(page_title="ESGFolio", layout="wide")

# Database connection
def get_db_connection():
    conn = sqlite3.connect('esgdb.db')
    conn.row_factory = sqlite3.Row
    return conn

# Session state
if 'username' not in st.session_state:
    st.session_state.username = None

# Helper functions
def authenticate_user(username, password):
    conn = get_db_connection()
    cursor = conn.cursor()
    user = cursor.execute('SELECT * FROM users WHERE username=? AND password=?', (username, password)).fetchone()
    conn.close()
    return user is not None

def register_user(username, name, email, password):
    conn = get_db_connection()
    cursor = conn.cursor()
    existing_user = cursor.execute('SELECT * FROM users WHERE username=? or email=?', (username, email)).fetchall()
    if existing_user:
        conn.close()
        return False
    else:
        cursor.execute('INSERT INTO users (username, name, email, password) VALUES (?, ?, ?, ?)', (username, name, email, password))
        conn.commit()
        conn.close()
        return True

def get_portfolio(username):
    conn = get_db_connection()
    portfolio = conn.execute('''SELECT 
                                company_name,
                                s.E_score AS escore,
                                s.S_score AS sscore,
                                s.G_score AS gscore,
                                (s.E_score + s.S_score + s.G_score) AS company_score
                              FROM portfolio p 
                              INNER JOIN Scores s ON p.company_name = s.Company 
                              WHERE username=?''', (username,)).fetchall()
    conn.close()
    return portfolio

def add_to_portfolio(username, company_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    existing = cursor.execute('SELECT * FROM portfolio WHERE username=? AND company_name=?', (username, company_name)).fetchall()
    if not existing:
        cursor.execute('INSERT INTO portfolio (username, company_name) VALUES (?, ?)', (username, company_name))
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False

def remove_from_portfolio(username, company_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM portfolio WHERE username=? AND company_name=?', (username, company_name))
    conn.commit()
    conn.close()

def search_companies(query, username):
    conn = get_db_connection()
    companies = conn.execute('''
        SELECT s.Company,
            CASE 
                WHEN p.username IS NOT NULL THEN 'Yes'
                ELSE 'No'
            END AS status
        FROM scores s
        LEFT JOIN portfolio p ON s.Company = p.company_name AND p.username = ?
        WHERE s.Company LIKE ?
    ''', (username, '%' + query + '%')).fetchall()
    conn.close()
    return companies

def generate_graphs(username):
    conn = get_db_connection()
    
    avg = conn.execute('''SELECT 
                            ROUND(AVG(s.E_score), 2),
                            ROUND(AVG(s.S_score), 2),
                            ROUND(AVG(s.G_score), 2),
                            ROUND(AVG(s.E_score + s.S_score + s.G_score), 2)
                           FROM portfolio p 
                           INNER JOIN Scores s ON p.company_name = s.Company''').fetchone()
    
    totalscore = conn.execute('''
    SELECT 
        ROUND(SUM(s.E_score)/count(*),2) AS e_score,
        ROUND(SUM(s.S_score)/count(*),2) AS s_score,
        ROUND(SUM(s.G_score)/count(*),2) AS g_score,
        ROUND((SUM(s.E_score) + SUM(s.S_score) + SUM(s.G_score))/count(*),2) AS portfolio_score
    FROM portfolio p 
    INNER JOIN Scores s ON p.company_name = s.Company 
    WHERE username=?
    ''', (username,)).fetchone()
    
    maxtot = conn.execute('''
    SELECT 
            MAX(tsc) AS max_tsc,
            MAX(esc) AS max_esc,
            MAX(ssc) AS max_ssc,
            MAX(gsc) AS max_gsc
    FROM (
        SELECT 
                p.username,
                AVG(s.e_score) AS esc,
                AVG(s.s_score) AS ssc,
                AVG(s.g_score) AS gsc,
                AVG(s.e_score + s.s_score + s.g_score) AS tsc
        FROM portfolio p 
        INNER JOIN Scores s ON p.company_name = s.Company 
        GROUP BY p.username
    ) as sub                    
    ''').fetchone()
    
    conn.close()
    
    labels = ['Environmental', 'Social', 'Governance']
    avg_scores = [(avg[0] * 10 / maxtot[1]), (avg[1] * 10 / maxtot[2]), (avg[2] * 10 / maxtot[3])]
    personal_scores = [(totalscore[0] * 10 / maxtot[1]), (totalscore[1] * 10 / maxtot[2]), (totalscore[2] * 10 / maxtot[3])]
    
    # Bar chart
    fig, ax = plt.subplots(figsize=(10, 6))
    x = range(len(labels))
    bar_width = 0.35
    ax.bar(x, avg_scores, width=bar_width, label='App Users Average', alpha=0.7)
    ax.bar([p + bar_width for p in x], personal_scores, width=bar_width, label='Personal Score', alpha=0.7)
    ax.set_xlabel('ESG Dimensions')
    ax.set_ylabel('Scores')
    ax.set_title('Comparison of ESG Scores')
    ax.set_xticks([p + bar_width / 2 for p in x])
    ax.set_xticklabels(labels)
    ax.legend()
    plt.tight_layout()
    
    # Radar chart
    fig2, ax2 = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))
    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    angles += angles[:1]
    avg_scores += avg_scores[:1]
    personal_scores += personal_scores[:1]
    ax2.fill(angles, avg_scores, color='blue', alpha=0.25)
    ax2.fill(angles, personal_scores, color='red', alpha=0.25)
    ax2.plot(angles, avg_scores, color='blue', linewidth=2, label='App Users Average')
    ax2.plot(angles, personal_scores, color='red', linewidth=2, label='Personal Score')
    ax2.set_yticklabels([])
    ax2.set_xticks(angles[:-1])
    ax2.set_xticklabels(labels)
    ax2.legend(loc='upper right', bbox_to_anchor=(0.1, 0.1))
    plt.title('Radar Chart for ESG Scores Comparison')
    
    return fig, fig2

# Main app
def main():
    logo = Image.open('static/FinalLogo_edited.png')
    st.sidebar.image(logo, width=200)

    if st.session_state.username is None:
        st.sidebar.title("ESGFolio")
        choice = st.sidebar.selectbox("Login/Signup", ['Login', 'Sign Up'])
        
        if choice == "Login":
            st.subheader("Login Section")
            username = st.text_input("User Name")
            password = st.text_input("Password", type='password')
            if st.button("Login"):
                if authenticate_user(username, password):
                    st.session_state.username = username
                    st.success("Logged In as {}".format(username))
                    st.rerun()
                else:
                    st.warning("Incorrect Username/Password")
                    
        elif choice == "Sign Up":
            st.subheader("Create New Account")
            new_user = st.text_input("Username")
            new_name = st.text_input("Name")
            new_password = st.text_input("Password", type='password')
            new_email = st.text_input("Email")
            if st.button("Signup"):
                if register_user(new_user, new_name, new_email, new_password):
                    st.success("You have successfully created an account")
                    st.info("Go to Login Menu to login")
                else:
                    st.warning("Username or email already exists")
    else:
        st.sidebar.title(f"Welcome {st.session_state.username}")
        menu = ["Dashboard", "Search", "Logout"]
        choice = st.sidebar.selectbox("Menu", menu)
        
        if choice == "Dashboard":
            st.title(f"{st.session_state.username}'s ESGFolio")
            
            portfolio = get_portfolio(st.session_state.username)
            if portfolio:
                df = pd.DataFrame(portfolio, columns=['Company', 'E Score', 'S Score', 'G Score', 'Total Score'])
                st.dataframe(df)
                
                fig1, fig2 = generate_graphs(st.session_state.username)
                st.pyplot(fig1)
                st.pyplot(fig2)
            else:
                st.info("Your portfolio is empty.")
            
            st.subheader("How Are Your Scores Calculated?")
            st.write("The scores each stock in your portfolio has received are scaled down to 10 using percentile methodology in comparison to all the stocks available in our database.")
            st.write("The total rating on the top is a percentile scoring against other users on the platform and their respective portfolios.")
            st.write("The colour ratings are also based on averages and medians on basis of stock percentiles and portfolio percentiles.")
            
        elif choice == "Search":
            st.subheader("Search Companies")
            search_query = st.text_input("Enter company name")
            if search_query:
                results = search_companies(search_query, st.session_state.username)
                if results:
                    for company in results:
                        col1, col2 = st.columns([3, 1])
                        col1.write(company[0])
                        if company[1] == 'No':
                            if col2.button("Add to Portfolio", key=company[0]):
                                if add_to_portfolio(st.session_state.username, company[0]):
                                    st.success(f"Added {company[0]} to your portfolio.")
                                else:
                                    st.info(f"{company[0]} is already in your portfolio.")
                        else:
                            col2.write("Already in portfolio")
                else:
                    st.info("No companies found.")
                    
        elif choice == "Logout":
            st.session_state.username = None
            st.rerun()

if __name__ == '__main__':
    main()
