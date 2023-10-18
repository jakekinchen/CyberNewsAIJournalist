"""
exploit_fetcher.py
------------------
determine_latest_exploit()
determine_oldest_exploit()
get_list_of_exploits()
upload_exploit(content)
fetch_latest_exploits()
fetch_past_exploits(quantity)
scrape_content(url, depth=1, include_links=True, is_external=False)

cisa.py
-------
get_exploits()
isolate_new_exploits(exploits)
format_json_for_supabase(exploits, catalog_version)
get_list_of_supabase_exploits()
insert_or_update_exploits(exploits)
get_cisa_exploits()
add_hyperlinks(url)
upload_hyperlinks()

content_optimization.py
-----------------------
tokenizer(string: str, encoding_name: str) -> int
model_optimizer(text, model)
seo_optimization(content)
assess_seo_needs(content)
generate_seo_prompt(metrics)
optimize_content(seo_prompt, content)
prioritize_topics(topics)
fetch_sources_from_query(query)
insert_tech_term_link(content: str, tech_term: str) -> str
generate_link_from_term(term)
select_tech_term_source(sources)
function_call_gpt(user_prompt, system_prompt, model, functions, function_call_mode='auto')
query_gpt(user_prompt, system_prompt='You are a response machine that only responds with the requested information', model='gpt-3.5-turbo')
create_factsheet(source, topic_name)
create_factsheets_for_sources(topic)
get_related_sources(topic_id)
update_external_source_info(topic_id, external_source_info)
remove_unrelated_sources(topic_name, external_source_info)
identify_unrelated_sources(topic_name, external_source_info)
delete_source(source_id)
remove_sources_from_supabase(unrelated_source_ids)
aggregate_factsheets(topic, combined_factsheet)
aggregate_factsheets_from_topic(topic)
regenerate_image_queries(post_info)

supabase_utils.py
-----------------

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
post_completion(post_info, functions)
post_synthesis(token, topic)
seo_optimization(content)
fetch_categories(token)
fetch_images_from_queries(search_queries: List[str], token: str, topic_id: int, prioritize_pexels: bool = False) -> List[Dict]
fetch_tags(token)
insert_tech_term_link(content: str, tech_term: str) -> str
function_call_gpt(user_prompt, system_prompt, model, functions, function_call_mode='auto')
inject_images_into_post_info(post_info, images, focus_keyword=None)
query_gpt(user_prompt, system_prompt='You are a response machine that only responds with the requested information', model='gpt-3.5-turbo')
insert_post_info_into_supabase(post_info)
regenerate_image_queries(post_info)

source_fetcher.py
-----------------
check_if_content_exceeds_limit(content)
gather_and_store_sources(supabase, url, topic_id, date_accessed, depth, existing_sources, accumulated_sources)
tokenizer(string: str, encoding_name: str) -> int
gather_sources(supabase, topic, MIN_SOURCES=2, overload=False, depth=2)
search_related_sources(query, offset=0)
search_related_articles(topic)
scrape_content(url, depth=1, include_links=True, is_external=False)
delete_targeted_sources(supabase, target_url)
delete_duplicate_source_urls(supabase)

init.py
-------
inspect_all_methods(ignore_methods=[])
generate_topics(supabase, amount_of_topics, gpt_ordering=False)
get_jwt_token(username, password)
gather_sources(supabase, topic, MIN_SOURCES=2, overload=False, depth=2)
post_synthesis(token, topic)
delete_topic(topic_id)
delete_supabase_post(topic_id)
create_wordpress_post(token, post_info, post_time)
process_topic(topic, token)
get_cisa_exploits()
test_scraping_site()
fetch_cisa_exploits()
main()
insert_post_info_into_supabase(post_info)
create_factsheets_for_sources(topic)

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
query_gpt(user_prompt, system_prompt='You are a response machine that only responds with the requested information', model='gpt-3.5-turbo')




--- Logging error ---
Traceback (most recent call last):
  File "/app/scripts/content_optimization.py", line 371, in aggregate_factsheets
    facts = query_gpt(user_prompt, system_prompt, model='gpt-3.5-turbo-16k')
  File "/app/scripts/content_optimization.py", line 216, in query_gpt
    response = openai.ChatCompletion.create(
  File "/usr/local/lib/python3.9/site-packages/openai/api_resources/chat_completion.py", line 25, in create
    return super().create(*args, **kwargs)
  File "/usr/local/lib/python3.9/site-packages/openai/api_resources/abstract/engine_api_resource.py", line 153, in create
    response, _, api_key = requestor.request(
  File "/usr/local/lib/python3.9/site-packages/openai/api_requestor.py", line 298, in request
    resp, got_stream = self._interpret_response(result, stream)
  File "/usr/local/lib/python3.9/site-packages/openai/api_requestor.py", line 700, in _interpret_response
    self._interpret_response_line(
  File "/usr/local/lib/python3.9/site-packages/openai/api_requestor.py", line 745, in _interpret_response_line
    raise error.ServiceUnavailableError(
openai.error.ServiceUnavailableError: The server is overloaded or not ready yet.

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/usr/local/lib/python3.9/logging/__init__.py", line 1083, in emit
    msg = self.format(record)
  File "/usr/local/lib/python3.9/logging/__init__.py", line 927, in format
    return fmt.format(record)
  File "/usr/local/lib/python3.9/logging/__init__.py", line 663, in format
    record.message = record.getMessage()
  File "/usr/local/lib/python3.9/logging/__init__.py", line 367, in getMessage
    msg = msg % self.args
TypeError: not all arguments converted during string formatting
Call stack:

  File "/app/scripts/init.py", line 178, in <module>
    asyncio.run(main())
  File "/usr/local/lib/python3.9/asyncio/runners.py", line 44, in run
    return loop.run_until_complete(main)
  File "/usr/local/lib/python3.9/asyncio/base_events.py", line 634, in run_until_complete
    self.run_forever()
  File "/usr/local/lib/python3.9/asyncio/base_events.py", line 601, in run_forever
    self._run_once()
  File "/usr/local/lib/python3.9/asyncio/base_events.py", line 1905, in _run_once
    handle._run()
  File "/usr/local/lib/python3.9/asyncio/events.py", line 80, in _run
    self._context.run(self._callback, *self._args)
  File "/app/scripts/init.py", line 171, in main
    await process_topic(topic, token)
  File "/app/scripts/init.py", line 93, in process_topic
    topic['factsheet'], topic['external_source_info'] = create_factsheets_for_sources(topic)
  File "/app/scripts/content_optimization.py", line 271, in create_factsheets_for_sources
    combined_factsheet = aggregate_factsheets(topic, combined_factsheet)
  File "/app/scripts/content_optimization.py", line 378, in aggregate_factsheets
    logging.error(f'Failed to synthesize factsheets for topic {topic["id"]}', gpt3_error)
Message: 'Failed to synthesize factsheets for topic 429'
Arguments: (ServiceUnavailableError(message='The server is overloaded or not ready yet.', http_status=503, request_id=None),)


"""