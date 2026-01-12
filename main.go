package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

// 1. Define the shape of your n8n payload
type Transaction struct {
	ID        string    `json:"id"`
	Vendor    string    `json:"vendor"`
	Amount    float64   `json:"amount"`
	Timestamp time.Time `json:"timestamp"`
}

// Global DB pool
var db *pgxpool.Pool

func main() {
	// --- DATABASE CONNECTION ---
	dbURL := os.Getenv("DATABASE_URL")
	if dbURL == "" {
		log.Fatal("DATABASE_URL is required")
	}

	config, err := pgxpool.ParseConfig(dbURL)
	if err != nil {
		log.Fatal("Unable to parse DB URL:", err)
	}

	db, err = pgxpool.NewWithConfig(context.Background(), config)
	if err != nil {
		log.Fatal("Unable to connect to database:", err)
	}
	defer db.Close()

	// --- AUTO-MIGRATION ---
	createTableSQL := `
	CREATE TABLE IF NOT EXISTS transactions (
		id TEXT PRIMARY KEY, 
		vendor TEXT NOT NULL,
		amount NUMERIC(10, 2) NOT NULL,
		timestamp TIMESTAMPTZ NOT NULL,
		created_at TIMESTAMPTZ DEFAULT NOW()
	);`
	
	_, err = db.Exec(context.Background(), createTableSQL)
	if err != nil {
		log.Fatal("Failed to create table:", err)
	}
	log.Println("✅ Database table 'transactions' is ready.")

	// --- ROUTES ---
	http.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte("LifeOS is healthy"))
	})

	http.HandleFunc("/transaction", handleTransaction)

	// --- SERVER START ---
	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	log.Printf("🚀 Server starting on port %s", port)
	if err := http.ListenAndServe(":"+port, nil); err != nil {
		log.Fatal(err)
	}
}

// 2. The Handler Function (Updated for Arrays)
func handleTransaction(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	// CHANGED: Decode into a SLICE of Transaction
	var transactions []Transaction
	if err := json.NewDecoder(r.Body).Decode(&transactions); err != nil {
		http.Error(w, "Invalid JSON payload", http.StatusBadRequest)
		log.Println("Error decoding JSON:", err)
		return
	}

	// Loop through the array and insert each one
	count := 0
	sql := `
	INSERT INTO transactions (id, vendor, amount, timestamp)
	VALUES ($1, $2, $3, $4)
	ON CONFLICT (id) DO NOTHING
	`

	for _, t := range transactions {
		_, err := db.Exec(context.Background(), sql, t.ID, t.Vendor, t.Amount, t.Timestamp)
		if err != nil {
			// If one fails, log it but continue processing the others
			log.Printf("Error inserting transaction %s: %v", t.ID, err)
			continue
		}
		count++
	}

	// Respond Success
	w.WriteHeader(http.StatusCreated)
	fmt.Fprintf(w, "Processed %d transaction(s)", count)
}