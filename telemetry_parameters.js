{
  "frame_sync_word": "0xABCD",
  "byte_order": ">", // 大端序
  "parameters": [
    {
      "name": "sync_word",
      "offset": 0,
      "length": 2,
      "struct_format": "H",
      "is_sync": true
    },
    {
      "name": "rocket_id",
      "offset": 2,
      "length": 1,
      "struct_format": "B"
    },
    {
      "name": "timestamp_s",
      "offset": 3,
      "length": 4,
      "struct_format": "I"
    },
    {
      "name": "altitude",
      "offset": 7,
      "length": 2,
      "struct_format": "H",
      "unit": "m",
      "scale_factor": 2.0
    },
    {
      "name": "velocity",
      "offset": 9,
      "length": 2,
      "struct_format": "H",
      "unit": "m/s",
      "scale_factor": 0.5
    },
    {
      "name": "engine_pressure",
      "offset": 11,
      "length": 2,
      "struct_format": "H",
      "unit": "kPa",
      "scale_factor": 10.0
    },
    {
      "name": "status_byte",
      "offset": 13,
      "length": 1,
      "struct_format": "B"
    },
    {
      "name": "checksum",
      "offset": 14,
      "length": 1,
      "struct_format": "B",
      "is_checksum": true
    }
  ],
  "frame_total_length": 15
}
