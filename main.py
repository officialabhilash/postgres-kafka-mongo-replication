from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel
from pymongo import MongoClient
from bson import ObjectId
import os
import json
import asyncio
from typing import Optional
from fastapi import Body

from pydantic import BaseModel


# Database configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://admin:root@localhost:5432/test"
)

# MongoDB configuration
MONGO_URL = os.getenv(
    "MONGO_URL",
    "mongodb://admin:root@localhost:27017/test"
)
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "test")

# Create SQLAlchemy engine
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Create MongoDB client
mongo_client = MongoClient(MONGO_URL)
mongo_db = mongo_client[MONGO_DB_NAME]


# Database Model
class Book(Base):
    __tablename__ = "books"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True, nullable=False)
    pages = Column(Integer, nullable=False)


# Pydantic schemas
class BookCreate(BaseModel):
    title: str
    pages: int


class BookResponse(BaseModel):
    id: int
    title: str
    pages: int
    
    class Config:
        from_attributes = True


# Create tables
Base.metadata.create_all(bind=engine)


# FastAPI app
app = FastAPI(title="Books API", version="1.0.0")


# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/")
def read_root():
    return {"message": "Welcome to Books API"}
@app.delete("/books/{book_id}", status_code=204)
def delete_book(book_id: int, db: Session = Depends(get_db)):
    """
    Delete a book from the database by its ID.

    - **book_id**: The ID of the book to delete
    """
    book = db.query(Book).filter(Book.id == book_id).first()
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")
    db.delete(book)
    db.commit()


@app.post("/books", response_model=BookResponse, status_code=201)
def create_book(book: BookCreate, db: Session = Depends(get_db)):
    """
    Create a new book in the database.
    
    - **title**: The title of the book
    - **pages**: The number of pages in the book
    """
    db_book = Book(title=book.title, pages=book.pages)
    db.add(db_book)
    db.commit()
    db.refresh(db_book)
    return db_book


@app.get("/books", response_model=list[BookResponse])
def get_books(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Get all books from the database.
    
    - **skip**: Number of records to skip (for pagination)
    - **limit**: Maximum number of records to return
    """
    books = db.query(Book).offset(skip).limit(limit).all()
    return books


@app.get("/books/{book_id}", response_model=BookResponse)
def get_book(book_id: int, db: Session = Depends(get_db)):
    """
    Get a specific book by ID.
    
    - **book_id**: The ID of the book to retrieve
    """
    book = db.query(Book).filter(Book.id == book_id).first()
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")
    return book


class BookUpdate(BaseModel):
    title: str | None = None
    pages: int | None = None

@app.patch("/books/{book_id}", response_model=BookResponse)
def update_book_partial(
    book_id: int,
    book_update: BookUpdate = Body(...),
    db: Session = Depends(get_db)
):
    """
    Partially update fields of a book record.
    
    - **book_id**: The ID of the book to update
    - **title**: (optional) New title of the book
    - **pages**: (optional) New number of pages for the book
    """
    book = db.query(Book).filter(Book.id == book_id).first()
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")
    update_data = book_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(book, field, value)
    db.commit()
    db.refresh(book)
    return book


@app.websocket("/ws/books")
async def websocket_books(websocket: WebSocket):
    """
    WebSocket endpoint that reads books from MongoDB and pushes new entries in real-time.
    Sends all books from MongoDB collection when client connects, then watches for new entries.
    """
    # Accept the websocket connection first
    await websocket.accept()
    
    # Send a connection confirmation immediately to complete handshake
    try:
        await websocket.send_json({
            "type": "connected",
            "message": "WebSocket connection established"
        })
    except Exception:
        # If we can't send, connection is already broken
        return
    
    # Helper function to safely send JSON
    async def safe_send_json(data: dict):
        """Safely send JSON, handling closed websocket"""
        try:
            await websocket.send_json(data)
        except (RuntimeError, WebSocketDisconnect, Exception):
            # Websocket is already closed or disconnected
            pass
    
    # Helper function to safely close websocket
    async def safe_close():
        """Safely close websocket if still connected"""
        try:
            await websocket.close()
        except (RuntimeError, WebSocketDisconnect, Exception):
            # Websocket is already closed or disconnected
            pass
    
    # Helper function to fetch books from MongoDB (async wrapper for blocking operation)
    async def fetch_books():
        """Fetch books from MongoDB in a separate thread to avoid blocking"""
        try:
            books_collection = mongo_db.books
            # Run blocking MongoDB operation in thread pool
            books = await asyncio.to_thread(lambda: list(books_collection.find({})))
            
            # Convert MongoDB documents to JSON-serializable format
            books_data = []
            for book in books:
                # Handle both old format (with envelope) and new format (direct data)
                if "after" in book:
                    # Old format with Debezium envelope - extract from 'after'
                    after_data = book.get("after", {})
                    book_data = {
                        "id": str(after_data.get("id", "")),
                        "title": after_data.get("title", ""),
                        "pages": int(after_data.get("pages", 0)) if after_data.get("pages") is not None else 0
                    }
                else:
                    # New format - direct data (after transform extracts 'after' field)
                    # _id should be the PostgreSQL id (set by PartialKeyStrategy)
                    # Also check for id field in case it's also present
                    doc_id = book.get("_id")
                    if doc_id is None:
                        doc_id = book.get("id")
                    book_data = {
                        "id": str(doc_id) if doc_id is not None else "",
                        "title": book.get("title", ""),
                        "pages": int(book.get("pages", 0)) if book.get("pages") is not None else 0
                    }
                books_data.append(book_data)
            return books_data
        except Exception as e:
            raise Exception(f"Error fetching books: {str(e)}")
    
    watch_task = None
    change_stream = None
    running = True
    
    try:
        # Get books collection from MongoDB
        books_collection = mongo_db.books
        
        # Fetch all books from MongoDB (non-blocking)
        books_data = await fetch_books()
        
        # Send initial books data to client
        await safe_send_json({
            "type": "books",
            "data": books_data,
            "count": len(books_data)
        })
        
        async def watch_changes_async():
            """Async wrapper for MongoDB change stream to watch for new book insertions"""
            nonlocal running, change_stream
            try:
                # Create change stream to watch for insertions
                change_stream = books_collection.watch([{"$match": {"operationType": "insert"}}])
                
                while running:
                    try:
                        # Use asyncio.to_thread to run the blocking change stream operation
                        change = await asyncio.to_thread(lambda: change_stream.try_next())
                        
                        if change is not None:
                            # New document inserted
                            full_document = change.get("fullDocument")
                            if full_document:
                                # Handle both old format (with envelope) and new format (direct data)
                                if "after" in full_document:
                                    # Old format with Debezium envelope
                                    after_data = full_document.get("after", {})
                                    book_data = {
                                        "id": str(after_data.get("id", "")),
                                        "title": after_data.get("title", ""),
                                        "pages": int(after_data.get("pages", 0)) if after_data.get("pages") is not None else 0
                                    }
                                else:
                                    # New format - direct data
                                    # _id should be the PostgreSQL id (set by PartialKeyStrategy)
                                    # Also check for id field in case it's also present
                                    doc_id = full_document.get("_id")
                                    if doc_id is None:
                                        doc_id = full_document.get("id")
                                    book_data = {
                                        "id": str(doc_id) if doc_id is not None else "",
                                        "title": full_document.get("title", ""),
                                        "pages": int(full_document.get("pages", 0)) if full_document.get("pages") is not None else 0
                                    }
                                
                                # Send new book to client
                                await safe_send_json({
                                    "type": "new_book",
                                    "data": book_data
                                })
                        else:
                            # No change detected, wait a bit before checking again
                            await asyncio.sleep(0.1)
                            
                    except asyncio.CancelledError:
                        break
                    except Exception as e:
                        if running:
                            await safe_send_json({
                                "type": "error",
                                "message": f"Error watching changes: {str(e)}"
                            })
                        break
            except Exception as e:
                if running:
                    await safe_send_json({
                        "type": "error",
                        "message": f"Change stream error: {str(e)}"
                    })
            finally:
                if change_stream is not None:
                    try:
                        change_stream.close()
                    except:
                        pass
        
        # Start watching for changes in background
        watch_task = asyncio.create_task(watch_changes_async())
        
        # Keep connection alive and listen for messages
        while True:
            try:
                # Wait for any message from client (can be used for filtering, etc.)
                message = await websocket.receive_text()
                
                # If client sends a request, send books again
                if message.lower() == "refresh":
                    # Fetch books asynchronously
                    books_data = await fetch_books()
                    
                    await safe_send_json({
                        "type": "books",
                        "data": books_data,
                        "count": len(books_data)
                    })
                    
            except WebSocketDisconnect:
                # Client disconnected, websocket is already closed
                running = False
                if watch_task:
                    watch_task.cancel()
                break
                
    except Exception as e:
        await safe_send_json({
            "type": "error",
            "message": str(e)
        })
    finally:
        running = False
        if watch_task:
            watch_task.cancel()
            try:
                await watch_task
            except asyncio.CancelledError:
                pass
        await safe_close()



if __name__ == "__main__":
    import uvicorn
    print("Starting server...")
    uvicorn.run(app, host="localhost", port=8000)