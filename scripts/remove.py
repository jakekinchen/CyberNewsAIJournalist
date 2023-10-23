"""content_optimization.py
-----------------------
seo_optimization(content)
function_call_gpt(user_prompt, system_prompt, model='gpt-3.5-turbo', functions=[], function_call_mode='auto')
assess_seo_needs(content)
generate_seo_prompt(metrics)
query_gpt(user_prompt, system_prompt, model='gpt-3.5-turbo')
optimize_content(seo_prompt, content)
insert_tech_term_link(content: str, tech_term: str) -> str
generate_link_from_term(term)
select_tech_term_source(sources)
regenerate_image_queries(post_info)
fetch_sources_from_query(query)

supabase_utils.py
-----------------
insert_post_info_into_supabase(post_info)
delete_topic(topic_id)
delete_supabase_post(topic_id)

image_fetcher.py
----------------
test_query_images()
resize_image(content, base_width, base_height)
upload_image_to_wordpress(token, image_url, image_type, origin_id)
fetch_photos_from_api(query, page, provider)
fetch_images_from_queries(search_queries: List[str], token: str, topic_id: int, prioritize_pexels: bool = False) -> List[Dict]
query_images(search_queries, list_of_supabase_images, provider)
process_photo(photo, query, provider)
fetch_image_type(image_url)
get_filename(origin_id: Union[str, int], image_type: str) -> str
get_list_of_supabase_images(provider)
is_photo_in_supabase(origin_id, list_of_supabase_images)
namedtuple(typename, field_names, *, rename=False, defaults=None, module=None)

remove.py
---------

test.py
-------

extract_text.py
---------------
get_proxy_url()
collect_diagnostic_info(url, proxy_url)
test_connection_without_ssl_verification(url)
test_ssl_handshake(url, proxy_url=None)
test_scraping_site()
scrape_content(url, depth=1, include_links=True, is_external=False)
establish_connection(url)
fetch_using_proxy(url, proxy_type=None, verify_ssl=False)
is_valid_http_url(url)
extract_external_links(soup, base_domain, depth)
exploit_db_content(soup)
urlparse(url, scheme='', allow_fragments=True)

utils.py
--------
inspect_all_methods(ignore_methods=[])

post_synthesis.py
-----------------
seo_optimization(content)
post_completion(post_info, functions)
function_call_gpt(user_prompt, system_prompt, model='gpt-3.5-turbo', functions=[], function_call_mode='auto')
post_synthesis(token, topic)
query_gpt(user_prompt, system_prompt, model='gpt-3.5-turbo')
insert_tech_term_link(content: str, tech_term: str) -> str
generate_wp_field_completion_function(categories, tags)
fetch_categories(token)
fetch_images_from_queries(search_queries: List[str], token: str, topic_id: int, prioritize_pexels: bool = False) -> List[Dict]
fetch_tags(token)
regenerate_image_queries(post_info)
inject_images_into_post_info(post_info, images, focus_keyword=None)

gpt_utils.py
------------
_api_call_with_backoff(*args, **kwargs)
function_call_gpt(user_prompt, system_prompt, model='gpt-3.5-turbo', functions=[], function_call_mode='auto')
query_gpt(user_prompt, system_prompt, model='gpt-3.5-turbo')
tokenizer(string: str, encoding_name: str) -> int
model_optimizer(text, model)
generate_factsheet_user_prompt(topic_name, content)
generate_wp_field_completion_function(categories, tags)
retry(*dargs: Any, **dkw: Any) -> Any

source_fetcher.py
-----------------
create_factsheet(source, topic_name)
function_call_gpt(user_prompt, system_prompt, model='gpt-3.5-turbo', functions=[], function_call_mode='auto')
create_factsheets_for_sources(topic)
query_gpt(user_prompt, system_prompt, model='gpt-3.5-turbo')
tokenizer(string: str, encoding_name: str) -> int
aggregate_factsheets(topic, combined_factsheet)
generate_factsheet_user_prompt(topic_name, content)
aggregate_factsheets_from_topic(topic)
get_related_sources(topic_id)
update_external_source_info(topic_id, external_source_info)
remove_unrelated_sources(topic_name, external_source_info)
scrape_content(url, depth=1, include_links=True, is_external=False)
identify_unrelated_sources(topic_name, external_source_info)
delete_source(source_id)
remove_sources_from_supabase(unrelated_source_ids)
fetch_sources_from_query(query)
check_if_content_exceeds_limit(content)
gather_and_store_sources(supabase, url, topic_id, date_accessed, depth, existing_sources, accumulated_sources)
gather_sources(supabase, topic, MIN_SOURCES=2, overload=False, depth=2)
search_related_sources(query, offset=0)
search_related_articles(topic)

init.py
-------
inspect_all_methods(ignore_methods=[])
insert_post_info_into_supabase(post_info)
generate_topics(supabase, amount_of_topics, gpt_ordering=False)
get_jwt_token(username, password)
post_synthesis(token, topic)
create_factsheets_for_sources(topic)
delete_topic(topic_id)
process_topic(topic, token)
create_wordpress_post(token, post_info, post_time)
get_cisa_exploits()
fetch_cisa_exploits()
test_scraping_site()
main()
gather_sources(supabase, topic, MIN_SOURCES=2, overload=False, depth=2)

wp_post.py
----------
add_tag_to_wordpress(token, tag)
create_wordpress_post(token, post_info, post_time)
fetch_categories(token)
fetch_tags(token)
fetch_wordpress_taxonomies(token)

generate_topics.py
------------------
fetch_and_process_xml(url)
filter_new_topics(topics, existing_topics)
get_ordered_topics(topics, amount_of_topics)
generate_topics(supabase, amount_of_topics, gpt_ordering=False)
query_gpt(user_prompt, system_prompt, model='gpt-3.5-turbo')
prioritize_topics(topics)
"""