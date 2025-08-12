from postgres_db import fetch_all, fetch_one, execute

async def get_all_candidates():
    """
    Retrieve all candidates.
    """
    query = "SELECT * FROM candidates ORDER BY id DESC"
    return await fetch_all(query)

async def get_candidate_by_id(candidate_id):
    """
    Retrieve a candidate by ID.
    """
    query = "SELECT * FROM candidates WHERE id = $1"
    return await fetch_one(query, [candidate_id])

async def create_candidate(name, email, phone=None, skills=None, experience=None, education=None):
    """
    Insert a new candidate.
    """
    query = """
        INSERT INTO candidates (name, email, phone, skills, experience, education)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING id
    """
    row = await fetch_one(query, [name, email, phone, skills, experience, education])
    return row["id"] if row else None

async def update_candidate(candidate_id, name=None, email=None, phone=None, skills=None, experience=None, education=None):
    """
    Update candidate details.
    """
    query = """
        UPDATE candidates
        SET name = COALESCE($2, name),
            email = COALESCE($3, email),
            phone = COALESCE($4, phone),
            skills = COALESCE($5, skills),
            experience = COALESCE($6, experience),
            education = COALESCE($7, education)
        WHERE id = $1
    """
    await execute(query, [candidate_id, name, email, phone, skills, experience, education])
    return True

async def delete_candidate(candidate_id):
    """
    Delete a candidate by ID.
    """
    query = "DELETE FROM candidates WHERE id = $1"
    await execute(query, [candidate_id])
    return True
