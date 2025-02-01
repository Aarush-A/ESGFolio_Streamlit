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

def color_code_score(score, avg, med):
    if score is None:
        return ''
    if score <= avg/2:
        return 'background-color: red'
    elif score <= med:
        return 'background-color: #FFD700'  # Gold
    else:
        return 'background-color: green'

def dashboard():
    st.title(f"{st.session_state.username}'s ESGFolio")
    
    conn = get_db_connection()
    
    # Fetch overall scores
    totalscore = conn.execute('''
        SELECT 
            ROUND(SUM(s.E_score)/count(*),2) AS e_score,
            ROUND(SUM(s.S_score)/count(*),2) AS s_score,
            ROUND(SUM(s.G_score)/count(*),2) AS g_score,
            ROUND((SUM(s.E_score) + SUM(s.S_score) + SUM(s.G_score))/count(*),2) AS portfolio_score
        FROM portfolio p 
        INNER JOIN Scores s ON p.company_name = s.Company 
        WHERE username=?
    ''', (st.session_state.username,)).fetchone()

    avgtot = conn.execute('''
        SELECT 
            CAST((AVG(tsc) - 0.5) + (AVG(tsc) > 0) AS INTEGER) AS avg_tsc,
    CAST((AVG(esc) - 0.5) + (AVG(esc) > 0) AS INTEGER) AS avg_esc,
    CAST((AVG(ssc) - 0.5) + (AVG(ssc) > 0) AS INTEGER) AS avg_ssc,
    CAST((AVG(gsc) - 0.5) + (AVG(gsc) > 0) AS INTEGER) AS avg_gsc
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

    # Display overall scores
    col1, col2, col3, col4 = st.columns(4)
    
    def display_score(col, score, max_score, avg_score, title):
        if score is not None and max_score is not None:
            normalized_score = (score * 10 / max_score)
            col.metric(title, f"{normalized_score:.2f}")
            if normalized_score <= avg_score/2:
                col.markdown(f"<div style='background-color: red; padding: 10px;'>{title}</div>", unsafe_allow_html=True)
            elif normalized_score <= avg_score:
                col.markdown(f"<div style='background-color: #FFD700; padding: 10px;'>{title}</div>", unsafe_allow_html=True)
            else:
                col.markdown(f"<div style='background-color: green; padding: 10px;'>{title}</div>", unsafe_allow_html=True)
        else:
            col.metric(title, "N/A")

    display_score(col1, totalscore[3], maxtot[0], avgtot[0], "ESG RATING")
    display_score(col2, totalscore[0], maxtot[1], avgtot[1], "Environmental RATING")
    display_score(col3, totalscore[1], maxtot[2], avgtot[2], "Social RATING")
    display_score(col4, totalscore[2], maxtot[3], avgtot[3], "Governmental RATING")

    # Fetch and display portfolio
    portfolio = get_portfolio(st.session_state.username)
    if portfolio:
        df = pd.DataFrame(portfolio, columns=['Company', 'E Score', 'S Score', 'G Score', 'Total Score'])
        
        # Fetch averages and medians for color coding
        conn = get_db_connection()
        avgs = conn.execute('SELECT AVG(e_score), AVG(s_score), AVG(g_score), AVG(e_score + s_score + g_score) FROM scores').fetchone()
        meds = conn.execute('SELECT AVG(e_score), AVG(s_score), AVG(g_score), AVG(e_score + s_score + g_score) FROM scores').fetchone()
        max_scores = conn.execute('SELECT MAX(e_score), MAX(s_score), MAX(g_score), MAX(e_score + s_score + g_score) FROM scores').fetchone()
        conn.close()

        # Normalize scores
        for i, col in enumerate(['E Score', 'S Score', 'G Score', 'Total Score']):
            df[col] = df[col].apply(lambda x: (x * 10 / max_scores[i]) if x is not None else None)

        # Apply color coding
        styled_df = df.style.applymap(lambda x: color_code_score(x, avgs[0], meds[0]), subset=['E Score'])
        styled_df = styled_df.applymap(lambda x: color_code_score(x, avgs[1], meds[1]), subset=['S Score'])
        styled_df = styled_df.applymap(lambda x: color_code_score(x, avgs[2], meds[2]), subset=['G Score'])
        styled_df = styled_df.applymap(lambda x: color_code_score(x, avgs[3], meds[3]), subset=['Total Score'])

        st.dataframe(styled_df)
        
        fig1, fig2 = generate_graphs(st.session_state.username)
        st.pyplot(fig1)
        st.pyplot(fig2)
    else:
        st.info("Your portfolio is empty.")

    st.subheader("How Are Your Scores Calculated?")
    st.write("The scores each stock in your portfolio has received are scaled down to 10 using percentile methodology in comparison to all the stocks available in our database.")
    st.write("The total rating on the top is a percentile scoring against other users on the platform and their respective portfolios.")
    st.write("The colour ratings are also based on averages and medians on basis of stock percentiles and portfolio percentiles.")

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
            dashboard()
            
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
