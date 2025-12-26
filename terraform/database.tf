resource "aws_s3_bucket" "assets" { bucket_prefix = "pos-assets-" }
resource "aws_s3_bucket_public_access_block" "pub" { bucket = aws_s3_bucket.assets.id; block_public_acls=false; block_public_policy=false; ignore_public_acls=false; restrict_public_buckets=false }
resource "aws_db_instance" "db" { 
  allocated_storage=20; engine="postgres"; instance_class="db.t3.micro"; 
  db_name="posdb"; username="admin"; password=var.db_pass; 
  publicly_accessible=false; skip_final_snapshot=true 
}