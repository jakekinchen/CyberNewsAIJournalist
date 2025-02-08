def store_post_info(self, post_info):
    """Store post information in Supabase."""
    try:
        # Check if image already exists
        existing_image = self.supabase.table('images').select('*').eq('id', post_info['featured_media']).execute()
        
        if not existing_image.data:  # Only insert if image doesn't exist
            image_data = {
                'id': post_info['featured_media'],
                'url': post_info['featured_media_url'],
                'type': 'image/png',
                'origin_id': str(post_info['featured_media'])
            }
            self.supabase.table('images').insert(image_data).execute()
        
        # Store post info
        post_data = {
            'id': post_info['id'],
            'title': post_info['title'],
            'content': post_info['content'],
            'featured_media': post_info['featured_media'],
            'featured_media_url': post_info['featured_media_url']
        }
        
        self.supabase.table('posts').insert(post_data).execute()
        print("Successfully stored post info in Supabase")
        
    except Exception as e:
        print(f"Failed to insert post: {e}")
        raise
 