create table books (
    id serial primary key,
    title varchar(255),
    pages int
);

CREATE USER cdc_user WITH REPLICATION ENCRYPTED PASSWORD 'root';

-- Grant read access to books table for CDC
GRANT SELECT ON TABLE books TO cdc_user;
GRANT USAGE ON SCHEMA public TO cdc_user;

ALTER TABLE books REPLICA IDENTITY USING INDEX books_pkey;

-- Create publication for CDC: we can use this publication 
-- to replicate the changes to the other database.
-- multiple tables can be replicated to the same publication.

CREATE PUBLICATION cdc_publication FOR TABLE books;

SELECT pg_create_logical_replication_slot('books_cdc_slot', 'pgoutput');

