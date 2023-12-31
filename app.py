from flask import Flask, request
import secrets 
from datetime import datetime
from threading import Lock

app = Flask(__name__)
state_lock = Lock()

# In-memory storage for posts
users = {}
posts = {}

# Endpoint 1
# Endpoint to create a post and Extension 3: Post as a Reply
@app.post("/post")
def create_post():
    with state_lock:
        try:
            # Parse and validate the JSON request
            data = request.get_json()
        except Exception:
            return {'err': 'Invalid JSON format'}, 400
        
        user_id = data.get('user_id')
        user_key = data.get('user_key')
        if(user_id!=None):
            username = users.get(user_id,None).get('username',None)

        replying_to_id = data.get('replying_to_id')
        
        if replying_to_id is not None and replying_to_id not in posts:
            return {'err': 'Reply to non-existent post'}, 404
        
        if 'msg' not in data:
            return {'err': 'Missing \'msg\' field'}, 400

        # Check if 'msg' field is not a string
        if not isinstance(data['msg'], str):
            return {'err': '\'msg\' must be a string'}, 400

        # Create a new post
        post_id = len(posts) + 1
        key = secrets.token_urlsafe(16)  # Generate a secure random key
        timestamp = datetime.utcnow().isoformat()  # ISO 8601 timestamp in UTC

        # Store the post
        posts[post_id] = {
            'id': post_id, 
            'key': key, 
            'timestamp': timestamp, 
            'msg': data['msg'], 
            'user_id': user_id,
            'username':username if(user_id!=None)else None,
            'user_key':user_key,
            'replying_to_id':replying_to_id
        }

    if replying_to_id is not None:
            posts[replying_to_id].setdefault('ids_of_replies', []).append(post_id)

    # Return the post data
    return {'id': post_id, 'key': key, 'timestamp': timestamp}, 200

#Endpoint 2
# Endpoint to get a post
@app.get("/post/<int:id>")
def read_post(id):
    with state_lock:
        # Check if the post exists
        if id not in posts:
            return {'err': "Post not found"}, 404
        post = posts[id]
        user = users.get(post.get('user_id'))
    return {
        'id': id, 
        'timestamp': post['timestamp'], 
        'msg': post['msg'],
        'user_id': post.get('user_id'),
        'username': user.get('username') if user else None,
        'replying_to_id': post.get('replying_to_id'),
        'ids_of_replies': post.get('ids_of_replies', [])
    }, 200

# Endpoint 3
# Endpoint to delete a post
@app.route('/post/<int:post_id>/delete/<key>', methods=['DELETE'])
def delete_post(post_id, key):
    with state_lock:
        # Check if the post exists
        if post_id not in posts:
            return {'err': 'Post not found'}, 404

        post = posts[post_id]
        user_id = post.get('user_id')

        if key != post['key'] and (user_id is None or key != users[user_id].get('key', '')):
            return {'err': 'Forbidden'}, 403

        del posts[post_id]

    return {'id': post_id, 'key': key, 'timestamp': post['timestamp']}, 200

# Endpoint 4: 
# Extension 1:- Endpoint to create a user
@app.route('/user', methods=['POST'])
def create_user():
    data = request.get_json()
    username = data.get('username')

    if any(user.get('username') == username for user in users.values()):
        return {'err': 'Username already exists'}, 400
    
    user_id = len(users) + 1
    user_key = secrets.token_urlsafe(16)
    real_name = data.get('real_name', '') #Optional real name

    users[user_id] = {'user_id': user_id, 'key': user_key, 'username': username, 'real_name': real_name}

    return {'user_id': user_id, 'key': user_key}, 200

# Endpoint 5:
# Extension 1:- Endpoint to get a user 
@app.route('/user/<identifier>', methods=['GET'])
def get_user_metadata(identifier):
    user = None

    if identifier.isdigit():
        user = users.get(int(identifier))
    else:
        user = next((usr for usr in users.values() if usr.get('username') == identifier), None)

    if not user:
        return {'err': 'User not found'}, 404
    
    return {
        'user_id': user['user_id'],
        'username': user['username'],
        'real_name': user['real_name'] 
    }, 200

# Endpoint 6: 
# Extension 2:- Endpoint to modify a user 
@app.route('/user/<int:user_id>', methods=['PUT'])
def edit_user_metadata(user_id):
    data = request.get_json()
    user_key = data.get('key')
    new_real_name = data.get('real_name')

    if user_id not in users or users[user_id]['key'] != user_key:
        return {'err': 'Invalid user or key'}, 403

    users[user_id]['real_name'] = new_real_name
    return {'msg': 'User metadata updated'}, 200

# Endpoint 7: 
# Extension 4: Endpoint to get All Posts for Date and Time based Range Queries  
@app.get("/posts/range")
def get_posts_by_range():
    start = request.args.get('start')
    end = request.args.get('end')
    
    # Convert string to datetime objects
    start_dt = datetime.fromisoformat(start) if start else None
    end_dt = datetime.fromisoformat(end) if end else None

    filtered_posts = []
    with state_lock:
        for post_id, post in posts.items():
            post_dt = datetime.fromisoformat(post['timestamp'])
            if (not start_dt or post_dt >= start_dt) and (not end_dt or post_dt <= end_dt):
                # Fetch user data
                user_data = users.get(post['user_id'], {})
                filtered_posts.append({
                    'id': post_id,
                    'timestamp': post['timestamp'],
                    'msg': post['msg'],
                    'user_id': post.get('user_id'),
                    'username': user_data.get('username'),
                    'replying_to_id': post.get('replying_to_id'),
                    'ids_of_replies': post.get('ids_of_replies', [])
                })
    return filtered_posts, 200

# Endpoint 8: 
# Extension 5: Endpoint to get All Posts of a given User
@app.get("/posts/user/<int:user_id>")
def get_posts_by_user(user_id):
    with state_lock:
        # Check if the user exists
        if user_id not in users:
            return {'err': 'User not found'}, 404

        # Filter posts by the given user ID
        user_posts = [
            {
                'id': post_id,
                'timestamp': post['timestamp'],
                'msg': post['msg'],
                'user_id': post.get('user_id'),
                'username': users[user_id]['username'],
                'replying_to_id': post.get('replying_to_id'),
                'ids_of_replies': post.get('ids_of_replies', [])
            }
            for post_id, post in posts.items() if post.get('user_id') == user_id
        ]

    return user_posts, 200


if __name__ == '__main__':
    app.run(debug=True)